"""
Scheduling module: data models and repository layer (spec §9).

Contents
--------
1. Models: User, Config, Availability, Recusal, Interview, ScheduleRun
   - Every datetime is timezone-aware and normalized to UTC on validation,
     and serialized to JSON as UTC (e.g. "2026-03-02T15:00:00Z").
2. Repository interface (`Repository`): abstract load_* / save_* functions.
   Services and routes depend only on this interface.
3. `JsonRepository`: implementation backed by JSON files in `backend/data/`.
   A Postgres/Supabase implementation can replace it later without touching
   services or routes.

Integrity rules enforced here
-----------------------------
- Recusals are unique per (interviewer_id, candidate_id) pair.
- At most one ScheduleRun may have status "published".
- All times are stored in UTC.

Requires: pydantic >= 2, Python >= 3.10.
Run `python scheduling_repository.py` to execute a self-check.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class RepositoryError(Exception):
    """Base class for all repository errors."""


class NotFoundError(RepositoryError):
    """Requested record does not exist."""


class ConflictError(RepositoryError):
    """A write would violate an integrity rule."""


class DuplicateRecusalError(ConflictError):
    """More than one recusal for the same (interviewer, candidate) pair."""


class InvalidDataError(RepositoryError):
    """Data passed to a save_* function is inconsistent."""


class StorageError(RepositoryError):
    """Stored data is unreadable or corrupt."""


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class Role(str, Enum):
    ADMIN = "admin"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class Phase(str, Enum):
    SETUP = "setup"
    INTERVIEWER_AVAILABILITY = "interviewer_availability"
    BOOKING = "booking"
    CLOSED = "closed"


class BookingStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    NEEDS_ATTENTION = "needs_attention"


# --------------------------------------------------------------------------- #
# Datetime handling: aware input only, always normalized to UTC
# --------------------------------------------------------------------------- #


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


# Naive datetimes are rejected (AwareDatetime); aware ones are converted to UTC.
UTCDateTime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class _Model(BaseModel):
    # Reject unknown keys so typos in the dummy JSON data surface early.
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class User(_Model):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    google_sub: str = Field(min_length=1)
    role: Role

class Config(_Model):
    """Scheduling config, one per cycle (§5). Edited by an admin in `setup`."""

    slot_length_min: int = Field(default=30, gt=0)
    interview_dates: list[date] = Field(min_length=1)
    timezone: str = "America/Chicago"

    daily_start_time: time
    daily_end_time: time

    interviewers_per_interview: int = Field(default = 2, ge=1)  # panel size k
    min_interviewer_minutes: int = Field(default=60, ge=0)

    max_interviews_per_interviewer: int | None = Field(default=None, ge=1)
    max_interviews_per_interviewer_per_day: int | None = Field(default=None, ge=1)

    rubric_url: str | None = None
    questions_doc_url: str | None = None

    phase: Phase = Phase.SETUP

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"unknown timezone: {v}") from exc
        return v

    @field_validator("interview_dates")
    @classmethod
    def _check_dates(cls, v: list[date]) -> list[date]:
        if len(set(v)) != len(v):
            raise ValueError("interview_dates must not contain duplicates")
        return sorted(v)

    @model_validator(mode="after")
    def _check_config(self):
        if self.daily_end_time <= self.daily_start_time:
            raise ValueError(
                "daily_end_time must be after daily_start_time"
            )

        total = self.max_interviews_per_interviewer
        daily = self.max_interviews_per_interviewer_per_day

        if total is not None and daily is not None and daily > total:
            raise ValueError(
                "daily interview cap cannot exceed total cap"
            )

        return self


class Availability(_Model):
    """One availability range. Used by both interviewers and candidates."""

    user_id: str = Field(min_length=1)
    start: UTCDateTime
    end: UTCDateTime

    @model_validator(mode="after")
    def _check_range(self) -> Availability:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class Recusal(_Model):
    interviewer_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    reason: str = ""

    @property
    def pair(self) -> tuple[str, str]:
        return (self.interviewer_id, self.candidate_id)

class Booking(_Model):
    id: str = Field(default_factory=_new_id, min_length=1)
    candidate_id: str = Field(min_length=1)

    start: UTCDateTime
    end: UTCDateTime

    interviewer_ids: list[str] = Field(min_length=1)

    status: BookingStatus = BookingStatus.CONFIRMED
    created_at: UTCDateTime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _check_booking(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")

        if len(set(self.interviewer_ids)) != len(
            self.interviewer_ids
        ):
            raise ValueError(
                "interviewer_ids must be unique"
            )

        return self
# --------------------------------------------------------------------------- #
# Repository interface
# --------------------------------------------------------------------------- #


class Repository(ABC):
    """
    Storage contract used by services and routes.

    `save_availability` and `save_recusals` use replace semantics: they replace
    everything stored for the given user, matching the `PUT /.../me` endpoints.
    """

    # users
    @abstractmethod
    def load_users(self) -> list[User]: ...

    @abstractmethod
    def save_users(self, users: list[User]) -> None: ...

    def get_user(self, user_id: str) -> User | None:
        """Convenience lookup (used by the stub auth to resolve roles)."""
        return next((u for u in self.load_users() if u.id == user_id), None)

    def get_user_by_google_sub(self, google_sub: str) -> User | None:
        return next(
            (
                user
                for user in self.load_users()
                if user.google_sub == google_sub
            ),
            None,
    )
    # config
    @abstractmethod
    def load_config(self) -> Config:
        """Raises NotFoundError if no config has been saved yet."""

    @abstractmethod
    def save_config(self, config: Config) -> None: ...

    # availability
    @abstractmethod
    def load_availability(self, user_id: str | None = None) -> list[Availability]:
        """Ranges for one user, or for everyone when user_id is None."""

    @abstractmethod
    def save_availability(self, user_id: str, ranges: list[Availability]) -> None:
        """Replace all ranges for `user_id`."""

    # recusals
    @abstractmethod
    def load_recusals(self, interviewer_id: str | None = None) -> list[Recusal]:
        """Recusals for one interviewer, or for everyone when None."""

    @abstractmethod
    def save_recusals(self, interviewer_id: str, recusals: list[Recusal]) -> None:
        """
        Replace all recusals for `interviewer_id`.
        Raises DuplicateRecusalError if a (interviewer, candidate) pair repeats.
        """

    @abstractmethod
    def load_bookings(self) -> list[Booking]:
        """Return all bookings."""
        ...

    @abstractmethod
    def get_booking(self, booking_id: str) -> Booking | None:
        """Return a booking by ID, or None if not found."""
        ...


# --------------------------------------------------------------------------- #
# Integrity helpers (shared by implementations)
# --------------------------------------------------------------------------- #


def check_unique_recusals(recusals: list[Recusal]) -> None:
    seen: set[tuple[str, str]] = set()
    for r in recusals:
        if r.pair in seen:
            raise DuplicateRecusalError(
                f"duplicate recusal for interviewer={r.interviewer_id!r}, "
                f"candidate={r.candidate_id!r}"
            )
        seen.add(r.pair)

# --------------------------------------------------------------------------- #
# JSON-backed implementation
# --------------------------------------------------------------------------- #

DEFAULT_DATA_DIR = Path("backend/data")


class JsonRepository(Repository):
    """
    Stores each collection in its own JSON file under `data_dir`:
    users.json, config.json, availability.json, recusals.json, bookings.json.

    Writes are atomic (temp file + os.replace) and guarded by a lock so
    concurrent requests in one process cannot interleave read-modify-write
    cycles. It is not safe across multiple processes; Postgres replaces it.
    """

    def __init__(self, data_dir: str | Path = DEFAULT_DATA_DIR) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # -- low-level IO ------------------------------------------------------- #

    def _path(self, name: str) -> Path:
        return self.data_dir / f"{name}.json"

    def _read_raw(self, name: str, default: Any) -> Any:
        path = self._path(name)
        if not path.exists():
            return default
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise StorageError(f"{path} is not valid JSON: {exc}") from exc

    def _write_raw(self, name: str, payload: Any) -> None:
        path = self._path(name)
        fd, tmp_name = tempfile.mkstemp(dir=self.data_dir, prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def _load_models(self, name: str, model: type[BaseModel]) -> list[Any]:
        raw = self._read_raw(name, [])
        if not isinstance(raw, list):
            raise StorageError(f"{self._path(name)} must contain a JSON list")
        try:
            return [model.model_validate(item) for item in raw]
        except ValidationError as exc:
            raise StorageError(f"{self._path(name)} contains invalid data: {exc}") from exc

    def _save_models(self, name: str, items: list[BaseModel]) -> None:
        self._write_raw(name, [m.model_dump(mode="json") for m in items])

    # -- users -------------------------------------------------------------- #

    def load_users(self) -> list[User]:
        with self._lock:
            return self._load_models("users", User)

    def save_users(self, users: list[User]) -> None:
        ids = [user.id for user in users]
        google_subs = [user.google_sub for user in users]

        if len(set(ids)) != len(ids):
            raise InvalidDataError("user ids must be unique")

        if len(set(google_subs)) != len(google_subs):
            raise InvalidDataError("google_sub values must be unique")

        with self._lock:
            self._save_models("users", users)

    # -- config ------------------------------------------------------------- #

    def load_config(self) -> Config:
        with self._lock:
            raw = self._read_raw("config", None)
            if raw is None:
                raise NotFoundError("no config has been saved yet")
            try:
                return Config.model_validate(raw)
            except ValidationError as exc:
                raise StorageError(f"{self._path('config')} contains invalid data: {exc}") from exc

    def save_config(self, config: Config) -> None:
        with self._lock:
            self._write_raw("config", config.model_dump(mode="json"))

    # -- availability ------------------------------------------------------- #

    def load_availability(self, user_id: str | None = None) -> list[Availability]:
        with self._lock:
            items = self._load_models("availability", Availability)
        if user_id is not None:
            items = [a for a in items if a.user_id == user_id]
        return items

    def save_availability(self, user_id: str, ranges: list[Availability]) -> None:
        if any(a.user_id != user_id for a in ranges):
            raise InvalidDataError(f"all ranges must belong to user {user_id!r}")
        with self._lock:
            others = [a for a in self._load_models("availability", Availability) if a.user_id != user_id]
            self._save_models("availability", others + list(ranges))

    # -- recusals ----------------------------------------------------------- #

    def load_recusals(self, interviewer_id: str | None = None) -> list[Recusal]:
        with self._lock:
            items = self._load_models("recusals", Recusal)
        if interviewer_id is not None:
            items = [r for r in items if r.interviewer_id == interviewer_id]
        return items

    def save_recusals(self, interviewer_id: str, recusals: list[Recusal]) -> None:
        if any(r.interviewer_id != interviewer_id for r in recusals):
            raise InvalidDataError(f"all recusals must belong to interviewer {interviewer_id!r}")
        check_unique_recusals(recusals)
        with self._lock:
            others = [r for r in self._load_models("recusals", Recusal) if r.interviewer_id != interviewer_id]
            combined = others + list(recusals)
            check_unique_recusals(combined)  # guards against pre-existing bad data
            self._save_models("recusals", combined)

    # -- bookings ------------------------------------------------------------- #

    def load_bookings(self) -> list[Booking]:
        with self._lock:
            return self._load_models("bookings", Booking)

    def get_booking(self, booking_id: str) -> Booking | None:
        return next(
            (
                booking
                for booking in self.load_bookings()
                if booking.id == booking_id
            ),
            None,
        )

# --------------------------------------------------------------------------- #
# Self-check
# --------------------------------------------------------------------------- #


def _self_check() -> None:
    from datetime import timedelta

    with tempfile.TemporaryDirectory() as tmp:
        repo = JsonRepository(tmp)

        # Test users without emails
        repo.save_users([
            User(
                id="admin1",
                name="Test Admin",
                google_sub="google-admin1",
                role=Role.ADMIN,
            ),
            User(
                id="interviewer1",
                name="Test Interviewer",
                google_sub="google-interviewer1",
                role=Role.INTERVIEWER,
            ),
            User(
                id="candidate1",
                name="Test Candidate",
                google_sub="google-candidate1",
                role=Role.CANDIDATE,
            ),
        ])

        assert repo.get_user("interviewer1") is not None
        assert repo.get_user_by_google_sub(
            "google-interviewer1"
        ).role == Role.INTERVIEWER

        # Test configuration
        config = Config(
            slot_length_min=30,
            interview_dates=[date(2026, 12, 1)],
            timezone="America/Chicago",
            daily_start_time="09:00",
            daily_end_time="17:00",
            interviewers_per_interview=2,
            min_interviewer_minutes=60,
        )

        repo.save_config(config)

        assert repo.load_config().slot_length_min == 30

        # Test long availability intervals
        start = datetime(
            2026, 12, 1, 15, 0,
            tzinfo=timezone.utc
        )

        availability = Availability(
            user_id="interviewer1",
            start=start,
            end=start + timedelta(hours=3),
        )

        repo.save_availability(
            "interviewer1",
            [availability],
        )

        assert len(
            repo.load_availability("interviewer1")
        ) == 1

        # Test recusals
        recusal = Recusal(
            interviewer_id="interviewer1",
            candidate_id="candidate1",
            reason="Conflict of interest",
        )

        repo.save_recusals(
            "interviewer1",
            [recusal],
        )

        assert len(
            repo.load_recusals("interviewer1")
        ) == 1

        # Test booking model
        booking = Booking(
            candidate_id="candidate1",
            start=start,
            end=start + timedelta(minutes=30),
            interviewer_ids=["interviewer1", "interviewer2"],
        )

        assert booking.status == BookingStatus.CONFIRMED
        assert len(booking.interviewer_ids) == 2

        # No booking has been saved yet
        assert repo.load_bookings() == []
        assert repo.get_booking("missing") is None

    print("All self-checks passed.")

if __name__ == "__main__":
    _self_check()
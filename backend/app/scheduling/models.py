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
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal
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


class PublishedRunExistsError(ConflictError):
    """Another run is already published (at most one is allowed)."""


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
    CANDIDATE_AVAILABILITY = "candidate_availability"
    SOLVING = "solving"
    PUBLISHED = "published"


class RunStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class BookingStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


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


class Violation(_Model):
    """A rule-check result for an admin edit or a draft run."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(pattern=r"^(error|warning)$")


class Edit(_Model):
    """Requested changes to one candidate's draft interview."""

    candidate_id: str = Field(min_length=1)
    start: UTCDateTime | None = None
    end: UTCDateTime | None = None
    interviewer_ids: list[str] | None = None
    unschedule: bool = False

    @model_validator(mode="after")
    def _check(self) -> Edit:
        if self.unschedule and any(value is not None for value in (self.start, self.end)):
            raise ValueError("an unschedule edit cannot include start or end")
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be provided together")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be after start")
        if self.interviewer_ids is not None:
            if not self.interviewer_ids:
                raise ValueError("interviewer_ids cannot be empty")
            if len(set(self.interviewer_ids)) != len(self.interviewer_ids):
                raise ValueError("interviewer_ids must be unique")
        if not self.unschedule and self.start is None and self.interviewer_ids is None:
            raise ValueError("an edit must change the interview or unschedule the candidate")
        return self


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class User(_Model):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    email: str
    role: Role

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email address")
        return v


class Config(_Model):
    """Scheduling config, one per cycle (§5). Edited by an admin in `setup`."""

    slot_length_min: int = Field(gt=0)
    interview_dates: list[date] = Field(min_length=1)
    timezone: str  # IANA name, e.g. "America/Chicago"
    interviewers_per_interview: int = Field(ge=1)  # panel size k
    min_candidate_slots: int = Field(ge=1)
    # Interviewer/admin-only links (spec §4); never returned to candidates.
    rubric_url: str | None = None
    questions_doc_url: str | None = None
    max_interviews_per_interviewer: int | None = Field(default=None, ge=1)
    max_interviews_per_interviewer_per_day: int | None = Field(default=None, ge=1)
    phase: Phase = Phase.SETUP

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"unknown IANA timezone: {v!r}") from exc
        return v

    @field_validator("interview_dates")
    @classmethod
    def _check_dates(cls, v: list[date]) -> list[date]:
        if len(set(v)) != len(v):
            raise ValueError("interview_dates must not contain duplicates")
        return sorted(v)

    @model_validator(mode="after")
    def _check_caps(self) -> Config:
        total = self.max_interviews_per_interviewer
        per_day = self.max_interviews_per_interviewer_per_day
        if total is not None and per_day is not None and per_day > total:
            raise ValueError(
                "max_interviews_per_interviewer_per_day cannot exceed "
                "max_interviews_per_interviewer"
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


class Interview(_Model):
    """A proposed or published interview. Belongs to a ScheduleRun."""

    candidate_id: str = Field(min_length=1)
    start: UTCDateTime
    end: UTCDateTime
    interviewer_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Interview:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if len(set(self.interviewer_ids)) != len(self.interviewer_ids):
            raise ValueError("interviewer_ids must be unique within a panel")
        return self


class Booking(_Model):
    """A confirmed or cancelled candidate interview booking."""

    id: str = Field(default_factory=_new_id, min_length=1)
    candidate_id: str = Field(min_length=1)
    start: UTCDateTime
    end: UTCDateTime
    interviewer_ids: list[str] = Field(min_length=1)
    status: BookingStatus = BookingStatus.CONFIRMED
    created_at: UTCDateTime = Field(default_factory=utcnow)
    location: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Booking:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if len(set(self.interviewer_ids)) != len(self.interviewer_ids):
            raise ValueError("interviewer_ids must be unique within a panel")
        return self


class BookingEvent(_Model):
    """A notification-safe description of a booking state change."""

    event_id: str = Field(default_factory=_new_id, min_length=1)
    event_type: Literal["booked", "cancelled", "rescheduled"] = "booked"
    booking: Booking
    previous_booking: Booking | None = None


class ScheduleRun(_Model):
    id: str = Field(default_factory=_new_id, min_length=1)
    created_at: UTCDateTime = Field(default_factory=utcnow)
    status: RunStatus = RunStatus.DRAFT
    interviews: list[Interview] = Field(default_factory=list)
    unscheduled_candidate_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> ScheduleRun:
        scheduled = [i.candidate_id for i in self.interviews]
        if len(set(scheduled)) != len(scheduled):
            raise ValueError("a candidate may have at most one interview per run")
        unscheduled = self.unscheduled_candidate_ids
        if len(set(unscheduled)) != len(unscheduled):
            raise ValueError("unscheduled_candidate_ids must be unique")
        if set(scheduled) & set(unscheduled):
            raise ValueError("a candidate cannot be both scheduled and unscheduled")
        return self

    def interviewer_loads(self) -> dict[str, int]:
        """Number of interviews per interviewer in this run (for admin review)."""
        loads: dict[str, int] = {}
        for interview in self.interviews:
            for iid in interview.interviewer_ids:
                loads[iid] = loads.get(iid, 0) + 1
        return loads


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

    # schedule runs
    @abstractmethod
    def load_runs(self) -> list[ScheduleRun]: ...

    @abstractmethod
    def load_run(self, run_id: str) -> ScheduleRun:
        """Raises NotFoundError if the run does not exist."""

    @abstractmethod
    def load_published_run(self) -> ScheduleRun | None: ...

    @abstractmethod
    def save_run(self, run: ScheduleRun) -> None:
        """
        Insert or update a run by id.
        Raises PublishedRunExistsError if `run` is published while a different
        run is already published.
        """


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


def check_single_published(run: ScheduleRun, existing: list[ScheduleRun]) -> None:
    if run.status != RunStatus.PUBLISHED:
        return
    for other in existing:
        if other.id != run.id and other.status == RunStatus.PUBLISHED:
            raise PublishedRunExistsError(
                f"run {other.id!r} is already published; only one run may be published"
            )


# --------------------------------------------------------------------------- #
# JSON-backed implementation
# --------------------------------------------------------------------------- #

DEFAULT_DATA_DIR = Path("backend/data")


class JsonRepository(Repository):
    """
    Stores each collection in its own JSON file under `data_dir`:
    users.json, config.json, availability.json, recusals.json, runs.json.

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
        ids = [u.id for u in users]
        if len(set(ids)) != len(ids):
            raise InvalidDataError("user ids must be unique")
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

    # -- schedule runs ------------------------------------------------------ #

    def load_runs(self) -> list[ScheduleRun]:
        with self._lock:
            return self._load_models("runs", ScheduleRun)

    def load_run(self, run_id: str) -> ScheduleRun:
        for run in self.load_runs():
            if run.id == run_id:
                return run
        raise NotFoundError(f"run {run_id!r} not found")

    def load_published_run(self) -> ScheduleRun | None:
        return next((r for r in self.load_runs() if r.status == RunStatus.PUBLISHED), None)

    def save_run(self, run: ScheduleRun) -> None:
        with self._lock:
            runs = self._load_models("runs", ScheduleRun)
            check_single_published(run, runs)
            for idx, existing in enumerate(runs):
                if existing.id == run.id:
                    runs[idx] = run
                    break
            else:
                runs.append(run)
            self._save_models("runs", runs)


# --------------------------------------------------------------------------- #
# Self-check
# --------------------------------------------------------------------------- #


def _self_check() -> None:
    from datetime import timedelta

    with tempfile.TemporaryDirectory() as tmp:
        repo = JsonRepository(tmp)

        # users
        repo.save_users([
            User(id="a1", name="Ada Admin", email="ada@example.com", role=Role.ADMIN),
            User(id="i1", name="Ian", email="ian@example.com", role=Role.INTERVIEWER),
            User(id="c1", name="Cy", email="cy@example.com", role=Role.CANDIDATE),
        ])
        assert repo.get_user("i1").role == Role.INTERVIEWER
        assert repo.get_user("nope") is None

        # config
        try:
            repo.load_config()
            raise AssertionError("expected NotFoundError")
        except NotFoundError:
            pass
        cfg = Config(
            slot_length_min=30, interview_dates=[date(2026, 3, 3), date(2026, 3, 2)],
            timezone="America/Chicago", interviewers_per_interview=2, min_candidate_slots=3,
        )
        repo.save_config(cfg)
        assert repo.load_config().interview_dates == [date(2026, 3, 2), date(2026, 3, 3)]
        try:
            Config(slot_length_min=30, interview_dates=[date(2026, 3, 2)], timezone="Mars/Base",
                   interviewers_per_interview=2, min_candidate_slots=1)
            raise AssertionError("expected bad timezone to fail")
        except ValidationError:
            pass

        # UTC normalization: input in Chicago time (UTC-6 in early March)
        chicago = timezone(timedelta(hours=-6))
        avail = Availability(user_id="i1", start=datetime(2026, 3, 2, 9, 0, tzinfo=chicago),
                             end=datetime(2026, 3, 2, 12, 0, tzinfo=chicago))
        assert avail.start == datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        assert avail.start.utcoffset() == timedelta(0)
        repo.save_availability("i1", [avail])
        stored = json.loads((Path(tmp) / "availability.json").read_text())
        assert stored[0]["start"] == "2026-03-02T15:00:00Z", stored
        assert repo.load_availability("i1")[0].start == avail.start
        try:
            Availability(user_id="i1", start=datetime(2026, 3, 2, 9, 0), end=datetime(2026, 3, 2, 10, 0))
            raise AssertionError("expected naive datetime to fail")
        except ValidationError:
            pass

        # replace semantics
        repo.save_availability("c1", [Availability(user_id="c1", start=avail.start, end=avail.end)])
        repo.save_availability("i1", [])
        assert repo.load_availability("i1") == [] and len(repo.load_availability("c1")) == 1

        # recusal uniqueness
        r = Recusal(interviewer_id="i1", candidate_id="c1", reason="former colleague")
        try:
            repo.save_recusals("i1", [r, r])
            raise AssertionError("expected DuplicateRecusalError")
        except DuplicateRecusalError:
            pass
        assert repo.load_recusals() == []  # failed write left nothing behind
        repo.save_recusals("i1", [r])
        repo.save_recusals("i1", [r])  # replace, not append
        assert len(repo.load_recusals("i1")) == 1

        # at most one published run
        t = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        iv = Interview(candidate_id="c1", start=t, end=t + timedelta(minutes=30), interviewer_ids=["i1"])
        run1 = ScheduleRun(interviews=[iv])
        run2 = ScheduleRun(unscheduled_candidate_ids=["c1"])
        repo.save_run(run1)
        repo.save_run(run2)
        assert len(repo.load_runs()) == 2 and repo.load_published_run() is None
        run1.status = RunStatus.PUBLISHED
        repo.save_run(run1)
        repo.save_run(run1)  # re-saving the same published run is fine
        run2.status = RunStatus.PUBLISHED
        try:
            repo.save_run(run2)
            raise AssertionError("expected PublishedRunExistsError")
        except PublishedRunExistsError:
            pass
        assert repo.load_published_run().id == run1.id
        assert repo.load_run(run1.id).interviewer_loads() == {"i1": 1}
        try:
            repo.load_run("missing")
            raise AssertionError("expected NotFoundError")
        except NotFoundError:
            pass

    print("All self-checks passed.")


if __name__ == "__main__":
    _self_check()
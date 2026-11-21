"""Person 3 outtake: read-only booking views built on Person 1/2 seams.

Everything here is a *reader*. Booking writes, slot eligibility, locking, and
load-count rules belong to Person 2 (``app/scheduling/bookings.py``); users,
roles, and config belong to Person 1 (``app/scheduling/repository.py``).

Two seams keep this module independent of their progress:

- ``BookingReader``: by default, delegates to Person 2's ``list_bookings()``,
  ``bookings_for_user()``, and ``interviewer_loads()`` when that module exists,
  and falls back to ``data/sample_bookings.json`` otherwise.
- ``load_context()``: prefers Person 1's ``load_inputs()``, then the shared
  ``JsonRepository``, then the same fixture.

Fixtures are a development fallback, not a source of truth.
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.scheduling.models import Booking, BookingStatus, Role, User, UTCDateTime

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Response models (Person 3's API contract)
# --------------------------------------------------------------------------- #


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterviewerLoad(_ResponseModel):
    id: str
    name: str | None
    load: int


class PanelMember(_ResponseModel):
    id: str
    name: str


class AdminBooking(_ResponseModel):
    id: str
    candidate_id: str
    candidate_name: str
    start: UTCDateTime
    end: UTCDateTime
    timezone: str
    status: BookingStatus
    interviewers: list[PanelMember]
    location: str | None = None


class AdminBookingOverview(_ResponseModel):
    timezone: str
    bookings: list[AdminBooking]
    unbooked_candidates: list[User]
    interviewer_loads: list[InterviewerLoad]


class MyInterview(_ResponseModel):
    """Candidate view. Has no rubric/questions fields, and extra="forbid"
    means they can never be added to a candidate response by accident."""

    status: Literal["scheduled", "not_scheduled"]
    candidate_id: str | None = None
    candidate_name: str | None = None
    start: UTCDateTime | None = None
    end: UTCDateTime | None = None
    timezone: str | None = None
    panel: list[PanelMember] = Field(default_factory=list)
    message: str | None = None


class InterviewerMyInterview(_ResponseModel):
    """Interviewer view: adds interviewer-only materials. Deliberately not a
    subclass of MyInterview so a candidate payload can never match this type."""

    status: Literal["scheduled", "not_scheduled"]
    candidate_id: str | None = None
    candidate_name: str | None = None
    start: UTCDateTime | None = None
    end: UTCDateTime | None = None
    timezone: str | None = None
    panel: list[PanelMember] = Field(default_factory=list)
    message: str | None = None
    rubric_url: str | None = None
    questions_doc_url: str | None = None


# --------------------------------------------------------------------------- #
# Booking reads (Person 2 seam)
# --------------------------------------------------------------------------- #

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_bookings.json"
_PERSON2_MODULE = "app.scheduling.bookings"


class BookingReader(Protocol):
    def list_bookings(self) -> list[Booking]: ...

    def bookings_for_user(self, user_id: str) -> list[Booking]: ...

    def interviewer_loads(self) -> dict[str, int]: ...


class FixtureBookingReader:
    """Reads ``data/sample_bookings.json``. Development/test only."""

    def list_bookings(self) -> list[Booking]:
        return [Booking.model_validate(b) for b in _load_fixture()["bookings"]]

    def bookings_for_user(self, user_id: str) -> list[Booking]:
        return [
            b
            for b in self.list_bookings()
            if b.candidate_id == user_id or user_id in b.interviewer_ids
        ]

    def interviewer_loads(self) -> dict[str, int]:
        loads: dict[str, int] = {}
        for booking in self.list_bookings():
            if booking.status != BookingStatus.CONFIRMED:
                continue
            for interviewer_id in booking.interviewer_ids:
                loads[interviewer_id] = loads.get(interviewer_id, 0) + 1
        return loads


def _default_reader() -> BookingReader:
    """Person 2's module if it provides the read contract, else fixtures."""
    try:
        module = importlib.import_module(_PERSON2_MODULE)
    except ImportError:
        return FixtureBookingReader()
    required = ("list_bookings", "bookings_for_user", "interviewer_loads")
    present = [name for name in required if callable(getattr(module, name, None))]
    if len(present) == len(required):
        return module  # type: ignore[return-value]
    if present:  # partially landed: worth surfacing; empty module is just "not yet"
        logger.warning("%s only provides %s; using fixture bookings", _PERSON2_MODULE, present)
    return FixtureBookingReader()


_booking_reader: BookingReader | None = None


def configure_booking_reader(reader: BookingReader | None) -> None:
    """Override the booking source (tests). ``None`` restores auto-detection."""
    global _booking_reader
    _booking_reader = reader


def _reader() -> BookingReader:
    return _booking_reader if _booking_reader is not None else _default_reader()


# --------------------------------------------------------------------------- #
# Users and config (Person 1 seam)
# --------------------------------------------------------------------------- #


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _live_inputs() -> tuple[Any, list[User]]:
    """Person 1's ``load_inputs()`` if present, else the shared JsonRepository."""
    try:
        repository = importlib.import_module("app.scheduling.repository")
        config, users, *_ = repository.load_inputs()
        return config, list(users)
    except ImportError:
        pass
    from app.scheduling.models import JsonRepository

    repo = JsonRepository()
    return repo.load_config(), repo.load_users()


def load_context() -> tuple[list[User], Any | None]:
    """Return ``(users, config)``. Config is whatever object Person 1 provides;
    read it with ``config_value`` so renamed or missing fields degrade to None."""
    try:
        config, users = _live_inputs()
        if users:
            return users, config
    except Exception as exc:  # noqa: BLE001 - any intake failure -> fixture
        logger.info("Live users/config unavailable (%s); using fixture", exc)
    data = _load_fixture()
    return [User.model_validate(u) for u in data["users"]], data.get("config", {})


def config_value(config: Any, name: str, default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def get_user(user_id: str) -> User | None:
    users, _ = load_context()
    return next((u for u in users if u.id == user_id), None)


# --------------------------------------------------------------------------- #
# Outtake views
# --------------------------------------------------------------------------- #


def _timezone(config: Any) -> str:
    return config_value(config, "timezone") or "UTC"


def _name(users_by_id: dict[str, User], user_id: str) -> str:
    user = users_by_id.get(user_id)
    return user.name if user else user_id


def _panel(booking: Booking, users_by_id: dict[str, User]) -> list[PanelMember]:
    return [PanelMember(id=i, name=_name(users_by_id, i)) for i in booking.interviewer_ids]


def list_unbooked_candidates() -> list[User]:
    users, _ = load_context()
    booked = {
        b.candidate_id
        for b in _reader().list_bookings()
        if b.status == BookingStatus.CONFIRMED
    }
    return [u for u in users if u.role == Role.CANDIDATE and u.id not in booked]


def get_admin_overview() -> AdminBookingOverview:
    users, config = load_context()
    timezone = _timezone(config)
    users_by_id = {u.id: u for u in users}
    reader = _reader()
    loads = reader.interviewer_loads()
    interviewer_ids = {u.id for u in users if u.role == Role.INTERVIEWER} | set(loads)

    return AdminBookingOverview(
        timezone=timezone,
        bookings=[
            AdminBooking(
                id=b.id,
                candidate_id=b.candidate_id,
                candidate_name=_name(users_by_id, b.candidate_id),
                start=b.start,
                end=b.end,
                timezone=timezone,
                status=b.status,
                interviewers=_panel(b, users_by_id),
                location=b.location,
            )
            for b in reader.list_bookings()
        ],
        unbooked_candidates=list_unbooked_candidates(),
        interviewer_loads=[
            InterviewerLoad(
                id=i,
                name=users_by_id[i].name if i in users_by_id else None,
                load=loads.get(i, 0),
            )
            for i in sorted(interviewer_ids)
        ],
    )


def list_my_interviews(user: User) -> list[MyInterview | InterviewerMyInterview]:
    """Role-filtered confirmed bookings for ``user``.

    Candidates get ``MyInterview`` (never rubric/questions links); interviewers
    get ``InterviewerMyInterview`` with the shared questions doc and rubric.
    """
    users, config = load_context()
    timezone = _timezone(config)
    users_by_id = {u.id: u for u in users}
    is_interviewer = user.role == Role.INTERVIEWER

    bookings = [
        b
        for b in _reader().bookings_for_user(user.id)
        if b.status == BookingStatus.CONFIRMED
        and (user.id in b.interviewer_ids if is_interviewer else b.candidate_id == user.id)
    ]

    if not bookings:
        if is_interviewer:
            return []
        return [
            MyInterview(
                status="not_scheduled",
                candidate_id=user.id,
                candidate_name=user.name,
                timezone=timezone,
                message="You have not booked an interview.",
            )
        ]

    result: list[MyInterview | InterviewerMyInterview] = []
    for b in sorted(bookings, key=lambda b: b.start):
        common = dict(
            status="scheduled",
            candidate_id=b.candidate_id,
            candidate_name=_name(users_by_id, b.candidate_id),
            start=b.start,
            end=b.end,
            timezone=timezone,
            panel=_panel(b, users_by_id),
        )
        if is_interviewer:
            result.append(
                InterviewerMyInterview(
                    **common,
                    rubric_url=config_value(config, "rubric_url"),
                    questions_doc_url=config_value(config, "questions_doc_url"),
                )
            )
        else:
            result.append(MyInterview(**common))
    return result


__all__ = [
    "AdminBooking",
    "AdminBookingOverview",
    "BookingReader",
    "FixtureBookingReader",
    "InterviewerLoad",
    "InterviewerMyInterview",
    "MyInterview",
    "PanelMember",
    "config_value",
    "configure_booking_reader",
    "get_admin_overview",
    "get_user",
    "list_my_interviews",
    "list_unbooked_candidates",
    "load_context",
]

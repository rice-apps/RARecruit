"""Data models for the scheduling module.

See backend/docs/scheduling-spec.md for how these fit together. Interviewers
submit fixed availability slots and the booking system assigns candidates a
panel at booking time.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum


class UserRole(str, Enum):
    """Role of a user, used for access checks on every endpoint."""

    ADMIN = "admin"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class Phase(str, Enum):
    """Scheduling cycle phase. Only an admin advances it, in this order."""

    SETUP = "setup"
    AVAILABILITY = "availability"
    SOLVING = "solving"
    PUBLISHED = "published"


class RunStatus(str, Enum):
    """Status of a solver run. At most one run is published."""

    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass
class Config:
    """Admin-set settings for one scheduling cycle.

    Attributes:
        slot_length_min: Length of every interview in minutes; defines the slot grid.
        interview_dates: Dates on which interviews may happen.
        timezone: IANA timezone used to interpret dates (times are stored in UTC).
        daily_start_time: Optional earliest time of day availability may start.
        daily_end_time: Optional latest time of day availability may end.
        interviewers_per_interview: Panel size for every interview.
        min_candidate_minutes: Minimum total availability a candidate must submit.
        min_interviewer_minutes: Minimum total availability an interviewer must submit.
        rubric_url: Optional link to the interview rubric.
        questions_doc_url: Optional link to the interviewer questions document.
        max_interviews_per_interviewer: Optional hard cap on total interviews per interviewer.
        max_interviews_per_interviewer_per_day: Optional hard cap per interviewer per day.
        phase: Current phase of the cycle.
    """

    interview_dates: list[date] = field(default_factory=list)
    slot_length_min: int = 30
    timezone: str = "America/Chicago"
    daily_start_time: time | None = None
    daily_end_time: time | None = None
    interviewers_per_interview: int = 2
    min_candidate_minutes: int = 60
    min_interviewer_minutes: int = 0
    rubric_url: str | None = None
    questions_doc_url: str | None = None
    max_interviews_per_interviewer: int | None = None
    max_interviews_per_interviewer_per_day: int | None = None
    phase: Phase = Phase.SETUP


@dataclass
class User:
    """An admin, interviewer, or candidate."""

    id: str
    name: str
    email: str
    role: UserRole


@dataclass
class Availability:
    """A time range when a user (interviewer or candidate) is available.

    Ranges need not align to the slot grid; only slots fully inside count.
    """

    user_id: str
    start: datetime
    end: datetime


@dataclass
class Recusal:
    """An interviewer who must not interview a given candidate (conflict of interest)."""

    interviewer_id: str
    candidate_id: str
    reason: str = ""


@dataclass
class Slot:
    """One cell of the slot grid: a fixed-length interval an interview can occupy."""

    start: datetime
    end: datetime


@dataclass
class Interview:
    """A candidate's assigned slot and interviewer panel within a solver run."""

    candidate_id: str
    start: datetime
    end: datetime
    interviewer_ids: list[str] = field(default_factory=list)


@dataclass
class ScheduleRun:
    """Output of one solver run, stored for admin review before publishing.

    Attributes:
        id: Run identifier.
        created_at: When the solver ran.
        status: Draft until an admin publishes it.
        interviews: Proposed interviews.
        unscheduled_candidate_ids: Candidates the solver could not place.
    """

    id: str
    created_at: datetime
    status: RunStatus = RunStatus.DRAFT
    interviews: list[Interview] = field(default_factory=list)
    unscheduled_candidate_ids: list[str] = field(default_factory=list)

"""
Intake models: User, Config, Availability, Recusal (spec §9).

- Every datetime is timezone-aware and normalized to UTC on validation,
  and serialized to JSON as UTC (e.g. "2026-03-02T15:00:00Z").
- Unknown keys are rejected so typos in the dummy JSON data surface early.

Requires: pydantic >= 2, Python >= 3.10.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class Role(str, Enum):
    ADMIN = "admin"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class Phase(str, Enum):
    SETUP = "setup"
    AVAILABILITY = "availability"
    SOLVING = "solving"
    PUBLISHED = "published"


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
    daily_start_time: time | None = None  # local time in `timezone`
    daily_end_time: time | None = None  # local time in `timezone`
    interviewers_per_interview: int = Field(ge=1)  # panel size k
    min_candidate_minutes: int = Field(ge=0)
    min_interviewer_minutes: int = Field(default=0, ge=0)
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

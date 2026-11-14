"""
Scheduling models: Slot, Interview, ScheduleRun (spec §9), plus the shared
types from ADR 0001 §7 (Violation, Edit, EditLogEntry).
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .intake import UTCDateTime, _Model, _new_id, utcnow

# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class RunStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"  # a time limit was hit before proving optimal
    INFEASIBLE = "infeasible"


class UnscheduledReason(str, Enum):
    """ADR §4.4."""

    NO_AVAILABILITY = "no_availability"
    NO_FULL_PANEL = "no_full_panel"
    RECUSALS = "recusals"
    CAPACITY = "capacity"
    MANUAL = "manual"


class Severity(str, Enum):
    BLOCK = "block"
    WARN = "warn"


class EditOp(str, Enum):
    MOVE = "move"
    SET_PANEL = "set_panel"
    UNSCHEDULE = "unschedule"
    PLACE = "place"


# --------------------------------------------------------------------------- #
# Slot grid
# --------------------------------------------------------------------------- #


class Slot(_Model):
    """One cell of the slot grid: a fixed-length interval an interview can occupy."""

    start: UTCDateTime
    end: UTCDateTime


# --------------------------------------------------------------------------- #
# Violations and edits (ADR §7)
# --------------------------------------------------------------------------- #


class Violation(_Model):
    code: str
    severity: Severity
    message: str
    candidate_id: str | None = None
    interviewer_id: str | None = None


class Edit(_Model):
    op: EditOp
    candidate_id: str = Field(min_length=1)
    start: UTCDateTime | None = None
    interviewer_ids: list[str] | None = None
    auto_panel: bool = False


class EditLogEntry(_Model):
    edit: Edit
    by_user_id: str = Field(min_length=1)
    at: UTCDateTime = Field(default_factory=utcnow)
    acknowledged_warnings: list[Violation] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


class Interview(_Model):
    """A proposed or published interview. Belongs to a ScheduleRun."""

    candidate_id: str = Field(min_length=1)
    start: UTCDateTime
    end: UTCDateTime
    interviewer_ids: list[str] = Field(min_length=1)
    manually_edited: bool = False

    @model_validator(mode="after")
    def _check(self) -> Interview:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if len(set(self.interviewer_ids)) != len(self.interviewer_ids):
            raise ValueError("interviewer_ids must be unique within a panel")
        return self


class ScheduleRun(_Model):
    id: str = Field(default_factory=_new_id, min_length=1)
    created_at: UTCDateTime = Field(default_factory=utcnow)
    status: RunStatus = RunStatus.DRAFT
    solver_status: SolverStatus = SolverStatus.OPTIMAL
    interviews: list[Interview] = Field(default_factory=list)
    unscheduled_candidate_ids: list[str] = Field(default_factory=list)
    unscheduled_reasons: dict[str, UnscheduledReason] = Field(default_factory=dict)
    edit_log: list[EditLogEntry] = Field(default_factory=list)

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

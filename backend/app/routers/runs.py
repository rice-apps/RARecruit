"""Admin run review/publication and current-user interview routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.scheduling.models import (
    ConflictError,
    Interview,
    JsonRepository,
    NotFoundError,
    Phase,
    Role,
    ScheduleRun,
    User,
)
from app.scheduling.notifications import NotificationResult, notify
from app.scheduling.runs import (
    list_runs,
    load_inputs,
    load_run,
    publish_run,
)

router = APIRouter()


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserSummary(_ResponseModel):
    id: str
    name: str
    email: str


class InterviewDetail(_ResponseModel):
    candidate_id: str
    candidate_name: str | None
    start: datetime
    end: datetime
    interviewers: list[UserSummary]


class InterviewerLoad(_ResponseModel):
    id: str
    name: str | None
    load: int


class RunSummary(_ResponseModel):
    id: str
    status: str
    phase: str
    timezone: str
    created_at: datetime
    scheduled_count: int
    unscheduled_count: int
    max_interviewer_load: int


class RunDetail(_ResponseModel):
    id: str
    status: str
    phase: str
    timezone: str
    created_at: datetime
    interviews: list[InterviewDetail]
    unscheduled_candidates: list[UserSummary]
    interviewer_loads: list[InterviewerLoad]


class PublishResponse(_ResponseModel):
    run: RunDetail
    emails_sent: int
    emails_written: int
    emails_skipped: int
    email_failures: list[str]


class PanelMember(_ResponseModel):
    id: str
    name: str


class MyInterview(_ResponseModel):
    status: Literal["scheduled", "not_scheduled"]
    candidate_id: str | None = None
    candidate_name: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    timezone: str | None = None
    panel: list[PanelMember] = Field(default_factory=list)
    message: str | None = None


def _require_admin(user_id: str | None) -> None:
    user = JsonRepository().get_user(user_id or "")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="admin role required")


def _summary(run: ScheduleRun, phase: Phase, timezone: str) -> RunSummary:
    loads = run.interviewer_loads()
    return RunSummary(
        id=run.id,
        status=run.status.value,
        phase=phase.value,
        timezone=timezone,
        created_at=run.created_at,
        scheduled_count=len(run.interviews),
        unscheduled_count=len(run.unscheduled_candidate_ids),
        max_interviewer_load=max(loads.values(), default=0),
    )


def _detail(
    run: ScheduleRun,
    users: list[User],
    phase: Phase,
    timezone: str,
) -> RunDetail:
    users_by_id = {user.id: user for user in users}
    loads = run.interviewer_loads()
    interviewer_ids = set(loads)
    interviewer_ids.update(user.id for user in users if user.role == Role.INTERVIEWER)
    for interview in run.interviews:
        interviewer_ids.update(interview.interviewer_ids)

    def user_summary(user: User) -> UserSummary:
        return UserSummary(id=user.id, name=user.name, email=user.email)

    interviews = [
        InterviewDetail(
            candidate_id=interview.candidate_id,
            candidate_name=users_by_id.get(interview.candidate_id).name
            if users_by_id.get(interview.candidate_id)
            else None,
            start=interview.start,
            end=interview.end,
            interviewers=[
                user_summary(users_by_id[interviewer_id])
                for interviewer_id in interview.interviewer_ids
                if interviewer_id in users_by_id
            ],
        )
        for interview in run.interviews
    ]
    unscheduled = [
        user_summary(users_by_id[candidate_id])
        for candidate_id in run.unscheduled_candidate_ids
        if candidate_id in users_by_id
    ]
    interviewer_loads = [
        InterviewerLoad(
            id=interviewer_id,
            name=users_by_id[interviewer_id].name
            if interviewer_id in users_by_id
            else None,
            load=loads.get(interviewer_id, 0),
        )
        for interviewer_id in sorted(interviewer_ids)
    ]
    return RunDetail(
        id=run.id,
        status=run.status.value,
        phase=phase.value,
        timezone=timezone,
        created_at=run.created_at,
        interviews=interviews,
        unscheduled_candidates=unscheduled,
        interviewer_loads=interviewer_loads,
    )


def _load_users() -> list[User]:
    try:
        return load_inputs()[1]
    except NotFoundError:
        return JsonRepository().load_users()


@router.get("/schedule/runs", response_model=list[RunSummary])
def get_runs(x_user_id: str | None = Header(default=None)) -> list[RunSummary]:
    _require_admin(x_user_id)
    config, _, _, _ = load_inputs()
    return [_summary(run, config.phase, config.timezone) for run in list_runs()]


@router.get("/schedule/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, x_user_id: str | None = Header(default=None)) -> RunDetail:
    _require_admin(x_user_id)
    try:
        config, users, _, _ = load_inputs()
        return _detail(load_run(run_id), users, config.phase, config.timezone)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/schedule/runs/{run_id}/publish", response_model=PublishResponse)
def publish(run_id: str, x_user_id: str | None = Header(default=None)) -> PublishResponse:
    _require_admin(x_user_id)
    try:
        load_run(run_id)
        config, users, _, _ = load_inputs()
        if config.phase != Phase.SOLVING:
            raise HTTPException(
                status_code=409,
                detail="runs can only be published during the solving phase",
            )
        published = publish_run(run_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        outcome = notify(published, users)
    except (OSError, RuntimeError, ValueError) as exc:
        outcome = NotificationResult(failures=[str(exc)])
    return PublishResponse(
        run=_detail(published, users, Phase.PUBLISHED, config.timezone),
        emails_sent=outcome.sent,
        emails_written=outcome.written,
        emails_skipped=outcome.skipped,
        email_failures=outcome.failures,
    )


@router.get("/interviews/me", response_model=list[MyInterview])
def get_my_interviews(x_user_id: str | None = Header(default=None)) -> list[MyInterview]:
    repository = JsonRepository()
    user = repository.get_user(x_user_id or "")
    if user is None or user.role not in (Role.INTERVIEWER, Role.CANDIDATE):
        raise HTTPException(status_code=403, detail="insufficient role")
    run = repository.load_published_run()
    if run is None:
        return []
    config, users, _, _ = load_inputs()
    users_by_id = {candidate.id: candidate for candidate in users}
    timezone = config.timezone
    display_zone = ZoneInfo(timezone)
    if user.role == Role.CANDIDATE:
        interviews = [interview for interview in run.interviews if interview.candidate_id == user.id]
    else:
        interviews = [
            interview
            for interview in run.interviews
            if user.id in interview.interviewer_ids
        ]

    def scheduled(interview: Interview) -> MyInterview:
        candidate_id = interview.candidate_id
        candidate = users_by_id.get(candidate_id)
        return MyInterview(
            status="scheduled",
            candidate_id=candidate_id,
            candidate_name=candidate.name if candidate else None,
            start=interview.start.astimezone(display_zone),
            end=interview.end.astimezone(display_zone),
            timezone=timezone,
            panel=[
                PanelMember(id=interviewer.id, name=interviewer.name)
                for interviewer_id in interview.interviewer_ids
                if (interviewer := users_by_id.get(interviewer_id)) is not None
            ],
        )

    if interviews:
        return [scheduled(interview) for interview in interviews]
    if user.role == Role.CANDIDATE:
        return [
            MyInterview(
                status="not_scheduled",
                candidate_id=user.id,
                candidate_name=user.name,
                timezone=timezone,
                message="You are not scheduled for an interview.",
            )
        ]
    return []

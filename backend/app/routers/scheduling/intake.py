
from fastapi import APIRouter, Header, HTTPException
from zoneinfo import ZoneInfo
from pathlib import Path

from app.scheduling.models import (
    JsonRepository,
    Config,
    Availability,
    Recusal,
    User,
    Role,
    Phase,
    NotFoundError,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "intake_test_data"
router = APIRouter()
repo = JsonRepository(DATA_DIR)


# -----------------------------------
# Authentication and authorization
# -----------------------------------

def get_current_user(x_user_id: str) -> User:
    user = repo.get_user(x_user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Unknown user"
        )

    return user


def require_role(user: User, allowed_roles: set[Role]) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


def require_phase(expected: Phase) -> None:
    config = repo.load_config()

    if config.phase != expected:
        raise HTTPException(
            status_code=409,
            detail=f"Operation only allowed during {expected.value}"
        )


# -----------------------------------
# Availability helper functions
# -----------------------------------

def merge_availability(
    ranges: list[Availability]
) -> list[Availability]:
    """Merge overlapping or touching availability ranges."""

    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    merged = [sorted_ranges[0]]

    for current in sorted_ranges[1:]:
        previous = merged[-1]

        if current.start <= previous.end:
            merged[-1] = Availability(
                user_id=previous.user_id,
                start=previous.start,
                end=max(previous.end, current.end)
            )
        else:
            merged.append(current)

    return merged


def validate_dates_and_window(
    ranges: list[Availability],
    config: Config
) -> None:
    """Ensure availability falls on allowed interview dates."""

    local_timezone = ZoneInfo(config.timezone)

    for availability in ranges:
        start = availability.start.astimezone(local_timezone)
        end = availability.end.astimezone(local_timezone)

        if start.date() not in config.interview_dates:
            raise HTTPException(
                status_code=422,
                detail="Availability must be on an interview date"
            )

        if start.date() != end.date():
            raise HTTPException(
                status_code=422,
                detail="Availability cannot cross midnight"
            )


def count_candidate_slots(
    ranges: list[Availability],
    slot_length_min: int
) -> int:
    """
    Count non-overlapping, full-length interview slots
    within each merged availability range.
    """

    total_slots = 0

    for availability in ranges:
        duration_minutes = (
            availability.end - availability.start
        ).total_seconds() / 60

        total_slots += int(duration_minutes // slot_length_min)

    return total_slots


def validate_candidate_slots(
    ranges: list[Availability],
    config: Config
) -> None:
    """Check the candidate's minimum number of available slots."""

    total_slots = count_candidate_slots(
        ranges,
        config.slot_length_min
    )

    if total_slots < config.min_candidate_slots:
        raise HTTPException(
            status_code=422,
            detail=(
                f"At least {config.min_candidate_slots} candidate "
                f"slots are required, but only {total_slots} "
                f"were provided"
            )
        )


# -----------------------------------
# Config endpoints
# -----------------------------------

@router.get("/config", response_model=Config)
def get_config():
    try:
        return repo.load_config()
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Scheduling configuration not found"
        )


@router.put("/config", response_model=Config)
def update_config(
    config: Config,
    x_user_id: str = Header(...)
):
    user = get_current_user(x_user_id)
    require_role(user, {Role.ADMIN})

    try:
        current_config = repo.load_config()
    except NotFoundError:
        current_config = None

    if current_config is not None:
        if current_config.phase != Phase.SETUP:
            raise HTTPException(
                status_code=409,
                detail="Configuration can only be updated during setup"
            )

    # Phase changes must go through /config/phase.
    updated = config.model_copy(
        update={"phase": Phase.SETUP}
    )

    repo.save_config(updated)
    return updated


# -----------------------------------
# Phase management
# -----------------------------------

@router.post("/config/phase", response_model=Config)
def advance_phase(x_user_id: str = Header(...)):
    user = get_current_user(x_user_id)
    require_role(user, {Role.ADMIN})

    try:
        config = repo.load_config()
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Scheduling configuration not found"
        )

    transitions = {
        Phase.SETUP: Phase.INTERVIEWER_AVAILABILITY,
        Phase.INTERVIEWER_AVAILABILITY: Phase.CANDIDATE_AVAILABILITY,
        Phase.CANDIDATE_AVAILABILITY: Phase.SOLVING,
    }

    if config.phase not in transitions:
        raise HTTPException(
            status_code=409,
            detail="Cannot advance phase from current state"
        )

    updated = config.model_copy(
        update={"phase": transitions[config.phase]}
    )

    repo.save_config(updated)
    return updated


# -----------------------------------
# Availability endpoints
# -----------------------------------

@router.get(
    "/availability/me",
    response_model=list[Availability]
)
def get_availability(x_user_id: str = Header(...)):
    user = get_current_user(x_user_id)
    require_role(user, {Role.INTERVIEWER, Role.CANDIDATE})

    return repo.load_availability(user.id)


@router.put(
    "/availability/me",
    response_model=list[Availability]
)
def update_availability(
    ranges: list[Availability],
    x_user_id: str = Header(...)
):
    user = get_current_user(x_user_id)
    require_role(user, {Role.INTERVIEWER, Role.CANDIDATE})

    # Each role has its own availability phase.
    if user.role == Role.INTERVIEWER:
        require_phase(Phase.INTERVIEWER_AVAILABILITY)
    else:
        require_phase(Phase.CANDIDATE_AVAILABILITY)

    # Verify that all ranges belong to the current user.
    for availability in ranges:
        if availability.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Cannot submit availability for another user"
            )

    config = repo.load_config()

    # Validate allowed interview dates.
    validate_dates_and_window(ranges, config)

    # Merge overlapping or touching ranges.
    merged = merge_availability(ranges)

    # The existing Config only specifies a candidate minimum.
    if user.role == Role.CANDIDATE:
        validate_candidate_slots(merged, config)

    # Replace this user's previous availability.
    repo.save_availability(user.id, merged)

    return merged


# -----------------------------------
# Recusal endpoints
# -----------------------------------

@router.get(
    "/recusals/me",
    response_model=list[Recusal]
)
def get_recusals(x_user_id: str = Header(...)):
    user = get_current_user(x_user_id)
    require_role(user, {Role.INTERVIEWER})

    return repo.load_recusals(user.id)


@router.put(
    "/recusals/me",
    response_model=list[Recusal]
)
def update_recusals(
    recusals: list[Recusal],
    x_user_id: str = Header(...)
):
    user = get_current_user(x_user_id)
    require_role(user, {Role.INTERVIEWER})
    require_phase(Phase.INTERVIEWER_AVAILABILITY)

    seen = set()

    for recusal in recusals:
        # Verify interviewer ownership.
        if recusal.interviewer_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Cannot submit recusals for another interviewer"
            )

        # Verify that the candidate exists.
        candidate = repo.get_user(recusal.candidate_id)

        if candidate is None or candidate.role != Role.CANDIDATE:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid candidate: {recusal.candidate_id}"
            )

        # Reject duplicate recusals.
        if recusal.candidate_id in seen:
            raise HTTPException(
                status_code=422,
                detail="Duplicate recusal"
            )

        seen.add(recusal.candidate_id)

    repo.save_recusals(user.id, recusals)

    return recusals

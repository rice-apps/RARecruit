"""Run persistence and publication services."""

from __future__ import annotations

from app.scheduling.models import (
    Availability,
    Config,
    JsonRepository,
    NotFoundError,
    Phase,
    PublishedRunExistsError,
    Recusal,
    Repository,
    RunStatus,
    ScheduleRun,
    User,
)


def _repository() -> Repository:
    return JsonRepository()


def save_run(run: ScheduleRun) -> None:
    """Insert or update a run by id.

    ``JsonRepository`` serializes the complete collection and replaces the
    destination only after the temporary file has been flushed and synced.
    """
    _repository().save_run(run)


def load_run(run_id: str) -> ScheduleRun:
    """Load a run or raise a clear error for an unknown id."""
    try:
        return _repository().load_run(run_id)
    except NotFoundError as exc:
        raise NotFoundError(f"schedule run {run_id!r} was not found") from exc


def list_runs() -> list[ScheduleRun]:
    """Return complete runs, newest first.

    The service returns full models so callers that need review details do not
    need a second load. The list endpoint can derive counts from each model;
    a summary DTO can be added later without changing persistence.
    """
    return sorted(
        _repository().load_runs(),
        key=lambda run: (run.created_at, run.id),
        reverse=True,
    )


def load_inputs() -> tuple[Config, list[User], list[Availability], list[Recusal]]:
    """Load the shared solver inputs, including named users and emails."""
    repository = _repository()
    return (
        repository.load_config(),
        repository.load_users(),
        repository.load_availability(),
        repository.load_recusals(),
    )


def publish_run(run_id: str) -> ScheduleRun:
    """Publish a run and advance the config phase.

    Publishing is rejected if any run is already published, including the
    requested run. Both repository writes use atomic file replacement.
    """
    repository = _repository()
    try:
        run = repository.load_run(run_id)
    except NotFoundError as exc:
        raise NotFoundError(f"schedule run {run_id!r} was not found") from exc
    existing = repository.load_published_run()
    if existing is not None:
        raise PublishedRunExistsError(
            f"schedule run {existing.id!r} is already published"
        )

    config = repository.load_config()
    published = run.model_copy(update={"status": RunStatus.PUBLISHED})
    published_config = config.model_copy(update={"phase": Phase.PUBLISHED})
    repository.save_run(published)
    repository.save_config(published_config)
    return published


__all__ = ["list_runs", "load_inputs", "load_run", "publish_run", "save_run"]

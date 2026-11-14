import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import runs as routes
from app.scheduling import runs as run_service
from app.scheduling.models import (
    Config,
    ConflictError,
    JsonRepository,
    NotFoundError,
    Phase,
    Role,
    RunStatus,
    ScheduleRun,
    User,
)


def _config(phase: Phase = Phase.SOLVING) -> Config:
    return Config(
        slot_length_min=30,
        interview_dates=[date(2026, 12, 1)],
        timezone="America/Chicago",
        interviewers_per_interview=2,
        min_candidate_slots=1,
        phase=phase,
    )


def _users() -> list[User]:
    return [
        User(id="admin", name="Admin", email="admin@example.com", role=Role.ADMIN),
        User(id="c1", name="Candidate", email="c1@example.com", role=Role.CANDIDATE),
        User(id="i1", name="Interviewer", email="i1@example.com", role=Role.INTERVIEWER),
    ]


def test_run_service_save_load_list_and_publish(monkeypatch, tmp_path):
    repository = JsonRepository(tmp_path)
    repository.save_config(_config())
    repository.save_users(_users())
    monkeypatch.setattr(run_service, "_repository", lambda: repository)
    monkeypatch.setattr(run_service, "load_inputs", lambda: (_config(), _users(), [], []))

    older = ScheduleRun(
        id="older",
        created_at=datetime(2026, 12, 1, tzinfo=UTC),
    )
    newer = ScheduleRun(
        id="newer",
        created_at=datetime(2026, 12, 2, tzinfo=UTC),
    )
    run_service.save_run(older)
    run_service.save_run(newer)
    assert [run.id for run in run_service.list_runs()] == ["newer", "older"]

    replacement = older.model_copy(update={"status": RunStatus.DRAFT})
    run_service.save_run(replacement)
    assert run_service.load_run("older").status is RunStatus.DRAFT

    with pytest.raises(NotFoundError, match="missing"):
        run_service.load_run("missing")

    published = run_service.publish_run("older")
    assert published.status is RunStatus.PUBLISHED
    assert repository.load_config().phase is Phase.PUBLISHED

    with pytest.raises(ConflictError):
        run_service.publish_run("newer")


def test_run_endpoints_enforce_role_phase_and_not_found(monkeypatch):
    class Repository:
        def get_user(self, user_id):
            return next((user for user in _users() if user.id == user_id), None)

    monkeypatch.setattr(routes, "JsonRepository", Repository)
    monkeypatch.setattr(routes, "list_runs", list)
    monkeypatch.setattr(routes, "load_inputs", lambda: (_config(), _users(), [], []))
    monkeypatch.setattr(routes, "load_run", lambda run_id: (_ for _ in ()).throw(NotFoundError("missing")))

    client = TestClient(app)
    assert client.get("/schedule/runs", headers={"X-User-Id": "c1"}).status_code == 403
    assert client.get("/schedule/runs/missing", headers={"X-User-Id": "admin"}).status_code == 404

    class PublishedConfig:
        phase = Phase.PUBLISHED
        timezone = "America/Chicago"

    monkeypatch.setattr(routes, "load_inputs", lambda: (PublishedConfig(), _users(), [], []))
    run = ScheduleRun(id="draft")
    monkeypatch.setattr(routes, "load_run", lambda run_id: run)
    assert (
        client.post("/schedule/runs/draft/publish", headers={"X-User-Id": "admin"}).status_code
        == 409
    )


def test_my_interviews_are_private_and_empty_before_publish(monkeypatch):
    users = _users()
    class Repository:
        def __init__(self, published=None):
            self.published = published

        def get_user(self, user_id):
            return next((user for user in users if user.id == user_id), None)

        def load_published_run(self):
            return self.published

    interview = {
        "candidate_id": "c1",
        "start": "2026-12-01T15:00:00Z",
        "end": "2026-12-01T15:30:00Z",
        "interviewer_ids": ["i1"],
    }
    published = ScheduleRun(interviews=[interview])
    monkeypatch.setattr(routes, "load_inputs", lambda: (_config(Phase.PUBLISHED), users, [], []))
    monkeypatch.setattr(routes, "JsonRepository", lambda: Repository(published))
    client = TestClient(app)

    response = client.get("/interviews/me", headers={"X-User-Id": "c1"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["timezone"] == "America/Chicago"

    monkeypatch.setattr(routes, "JsonRepository", lambda: Repository(None))
    assert client.get("/interviews/me", headers={"X-User-Id": "c1"}).json() == []
    assert client.get("/interviews/me", headers={"X-User-Id": "admin"}).status_code == 403


def test_sample_run_is_a_complete_published_fixture():
    sample = json.loads(
        (Path(__file__).parents[1] / "data" / "sample_run.json").read_text()
    )
    run = ScheduleRun.model_validate(sample)
    assert run.status is RunStatus.PUBLISHED
    assert run.interviewer_loads()["i1"] == 3
    assert run.unscheduled_candidate_ids == ["c4"]

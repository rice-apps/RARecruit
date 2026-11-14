from datetime import UTC, date, datetime

import googleapiclient.discovery
import pytest

from app.scheduling import notifications
from app.scheduling.models import Config, Interview, Role, RunStatus, ScheduleRun, User


@pytest.mark.parametrize("value", ["", "invalid", "true", "1"])
def test_invalid_email_dry_run_values_stay_safe(monkeypatch, value):
    monkeypatch.setenv("EMAIL_DRY_RUN", value)

    assert notifications._dry_run_enabled()


def test_email_dry_run_defaults_safe(monkeypatch, tmp_path):
    class Repository:
        def load_config(self):
            return Config(
                slot_length_min=30,
                interview_dates=[date(2026, 12, 1)],
                timezone="America/Chicago",
                interviewers_per_interview=2,
                min_candidate_slots=1,
            )

    def fail_if_gmail_is_loaded(*args, **kwargs):
        raise AssertionError("Gmail must not be loaded in dry-run mode")

    user = User(
        id="candidate-1",
        name="Candidate",
        email="candidate@example.com",
        role=Role.CANDIDATE,
    )
    monkeypatch.delenv("EMAIL_DRY_RUN", raising=False)
    monkeypatch.setattr(notifications, "JsonRepository", Repository)
    monkeypatch.setattr(
        notifications,
        "_recipients",
        lambda *args: [
            notifications._Recipient(
                user=user,
                subject="Test",
                body="This is a dry-run message.",
            )
        ],
    )
    monkeypatch.setattr(googleapiclient.discovery, "build", fail_if_gmail_is_loaded)
    monkeypatch.chdir(tmp_path)

    result = notifications.notify(
        notifications.ScheduleRun(id="dry-run-guard"),
        [],
    )

    assert result.sent == 0
    assert result.written == 1
    assert not result.failures


def test_notifications_group_interviewer_and_skip_missing_email(monkeypatch, tmp_path):
    class Repository:
        def load_config(self):
            return Config(
                slot_length_min=30,
                interview_dates=[date(2026, 12, 1)],
                timezone="America/Chicago",
                interviewers_per_interview=2,
                min_candidate_slots=1,
            )

    users = [
        User(id="c1", name="Candidate One", email="c1@example.com", role=Role.CANDIDATE),
        User(id="c2", name="Candidate Two", email="c2@example.com", role=Role.CANDIDATE),
        User(id="i1", name="Interviewer One", email="i1@example.com", role=Role.INTERVIEWER),
        User(id="i2", name="No Email", email="i2@example.com", role=Role.INTERVIEWER),
    ]
    start = datetime(2026, 12, 1, 15, tzinfo=UTC)
    run = ScheduleRun(
        id="grouped",
        status=RunStatus.PUBLISHED,
        interviews=[
            Interview(
                candidate_id="c1",
                start=start,
                end=start.replace(minute=30),
                interviewer_ids=["i1", "i2"],
            ),
            Interview(
                candidate_id="c2",
                start=start.replace(hour=16),
                end=start.replace(hour=16, minute=30),
                interviewer_ids=["i1", "i2"],
            ),
        ],
    )
    users[-1] = User.model_construct(
        id="i2",
        name="No Email",
        email="",
        role=Role.INTERVIEWER,
    )
    monkeypatch.setattr(notifications, "JsonRepository", Repository)
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")
    monkeypatch.chdir(tmp_path)

    result = notifications.notify(run, users)

    assert result.written == 3
    assert result.skipped == 1
    interviewer_message = next(
        (tmp_path / "backend/data/outbox").glob("grouped-i1-*.eml")
    ).read_text()
    assert "Candidate One" in interviewer_message
    assert "Candidate Two" in interviewer_message
    assert "9:00 AM" in interviewer_message


def test_gmail_failure_is_per_recipient(monkeypatch, tmp_path):
    class Repository:
        def load_config(self):
            return Config(
                slot_length_min=30,
                interview_dates=[date(2026, 12, 1)],
                timezone="America/Chicago",
                interviewers_per_interview=2,
                min_candidate_slots=1,
            )

    users = [
        User(id="c1", name="Candidate One", email="c1@example.com", role=Role.CANDIDATE),
        User(id="c2", name="Candidate Two", email="c2@example.com", role=Role.CANDIDATE),
        User(id="i1", name="Interviewer", email="i1@example.com", role=Role.INTERVIEWER),
    ]
    start = datetime(2026, 12, 1, 15, tzinfo=UTC)
    run = ScheduleRun(
        id="gmail-failure",
        interviews=[
            Interview(
                candidate_id="c1",
                start=start,
                end=start.replace(minute=30),
                interviewer_ids=["i1"],
            ),
            Interview(
                candidate_id="c2",
                start=start.replace(hour=16),
                end=start.replace(hour=16, minute=30),
                interviewer_ids=["i1"],
            ),
        ],
    )

    class Sender:
        def __init__(self):
            self.calls = 0

        def users(self):
            return self

        def messages(self):
            return self

        def send(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("temporary Gmail failure")
            return self

        def execute(self):
            return {}

    sender = Sender()
    monkeypatch.setattr(notifications, "JsonRepository", Repository)
    monkeypatch.setattr(googleapiclient.discovery, "build", lambda *args, **kwargs: sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "false")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.chdir(tmp_path)

    result = notifications.notify(run, users)

    assert sender.calls == 3
    assert result.sent == 2
    assert len(result.failures) == 1

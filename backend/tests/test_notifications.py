from datetime import UTC, datetime

import googleapiclient.discovery
import pytest

from app.scheduling import notifications
from app.scheduling.models import Booking, BookingEvent, Role, User

_CONFIG = {"timezone": "America/Chicago"}
_USERS = [
    User(id="c1", name="Alex", email="alex@example.com", role=Role.CANDIDATE),
    User(id="i1", name="Ana", email="ana@example.com", role=Role.INTERVIEWER),
    User(id="i2", name="Ben", email="ben@example.com", role=Role.INTERVIEWER),
]


def _event(event_id: str = "event-1", **booking_kwargs) -> BookingEvent:
    start = datetime(2026, 12, 1, 15, tzinfo=UTC)
    booking = Booking(
        id="booking-c1",
        candidate_id="c1",
        start=start,
        end=start.replace(minute=30),
        interviewer_ids=["i1", "i2"],
        **booking_kwargs,
    )
    return BookingEvent(event_id=event_id, event_type="booked", booking=booking)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Person 1's users/config come through load_context; stub it."""
    monkeypatch.setattr(notifications, "load_context", lambda: (_USERS, _CONFIG))
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("value", ["", "invalid", "true", "1"])
def test_invalid_email_dry_run_values_stay_safe(monkeypatch, value):
    monkeypatch.setenv("EMAIL_DRY_RUN", value)
    assert notifications._dry_run_enabled()


def test_dry_run_is_default_and_never_loads_gmail(monkeypatch, tmp_path):
    def fail_if_gmail_is_loaded(*args, **kwargs):
        raise AssertionError("Gmail must not be loaded in dry-run mode")

    monkeypatch.delenv("EMAIL_DRY_RUN", raising=False)
    monkeypatch.setattr(googleapiclient.discovery, "build", fail_if_gmail_is_loaded)

    result = notifications.notify_booking_event(_event())

    assert result.sent == 0
    assert result.written == 3
    assert not result.failures


def test_contract_call_with_event_only_is_idempotent(monkeypatch, tmp_path):
    """Person 2 calls notify_booking_event(event) with no users argument."""
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    first = notifications.notify_booking_event(_event(location="Room 101"))
    second = notifications.notify_booking_event(_event(location="Room 101"))

    assert (first.written, first.skipped, first.failures) == (3, 0, [])
    assert second.written == 0
    messages = list((tmp_path / "backend/data/outbox").glob("event-1-*.eml"))
    assert len(messages) == 3
    candidate = next(p for p in messages if "-c1-" in p.name).read_text()
    assert "9:00 AM" in candidate and "Room 101" in candidate


def test_reschedule_notifies_dropped_interviewers(monkeypatch, tmp_path):
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")
    old = _event().booking
    new = old.model_copy(
        update={"start": old.start.replace(hour=17), "end": old.end.replace(hour=17), "interviewer_ids": ["i1"]}
    )
    event = BookingEvent(
        event_id="resched-1", event_type="rescheduled", booking=new, previous_booking=old
    )

    result = notifications.notify_booking_event(event)

    assert result.written == 3  # candidate, i1 (still on panel), i2 (dropped)
    dropped = next((tmp_path / "backend/data/outbox").glob("resched-1-i2-*.eml")).read_text()
    assert "cancelled" in dropped and "9:00 AM" in dropped


def test_skips_missing_email(monkeypatch):
    users = [
        _USERS[0],
        _USERS[1],
        User.model_construct(id="i2", name="Ben", email="", role=Role.INTERVIEWER),
    ]
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    result = notifications.notify_booking_event(_event(), users)

    assert result.written == 2
    assert result.skipped == 1


def test_never_raises_into_booking_path(monkeypatch):
    def broken_context():
        raise RuntimeError("intake storage unavailable")

    monkeypatch.setattr(notifications, "load_context", broken_context)

    result = notifications.notify_booking_event(_event())

    assert result.sent == result.written == 0
    assert result.failures and "intake storage unavailable" in result.failures[0]


def test_gmail_failure_is_per_recipient(monkeypatch):
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
    monkeypatch.setattr(googleapiclient.discovery, "build", lambda *args, **kwargs: sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "false")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")

    result = notifications.notify_booking_event(_event())

    assert sender.calls == 3
    assert result.sent == 2
    assert len(result.failures) == 1

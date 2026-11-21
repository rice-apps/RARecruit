"""Person 3 outtake views, run against fixtures with Person 1/2 seams isolated."""

import sys
import types
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scheduling import outtake
from app.scheduling.models import Booking, Config, Role, User


@pytest.fixture(autouse=True)
def _fixture_sources(monkeypatch):
    """Force fixture users/config/bookings regardless of what P1/P2 have landed."""

    def no_live_inputs():
        raise FileNotFoundError("no live intake data in tests")

    monkeypatch.setattr(outtake, "_live_inputs", no_live_inputs)
    outtake.configure_booking_reader(outtake.FixtureBookingReader())
    yield
    outtake.configure_booking_reader(None)


def test_admin_booking_overview_and_csv():
    client = TestClient(app)

    response = client.get("/admin/bookings", headers={"X-User-Id": "admin"})
    assert response.status_code == 200
    overview = response.json()
    assert len(overview["bookings"]) == 2
    assert [c["id"] for c in overview["unbooked_candidates"]] == ["c3", "c4"]
    assert {l["id"]: l["load"] for l in overview["interviewer_loads"]} == {
        "i1": 2,
        "i2": 1,
        "i3": 1,
    }

    assert client.get("/admin/bookings", headers={"X-User-Id": "c1"}).status_code == 403
    csv_response = client.get("/admin/bookings.csv", headers={"X-User-Id": "admin"})
    assert csv_response.status_code == 200
    assert "Alex" in csv_response.text
    assert "Ana; Ben" in csv_response.text


def test_my_interviews_are_role_specific_and_candidate_private():
    client = TestClient(app)

    candidate = client.get("/interviews/me", headers={"X-User-Id": "c1"})
    assert candidate.status_code == 200
    assert len(candidate.json()) == 1
    assert candidate.json()[0]["candidate_id"] == "c1"
    assert "rubric_url" not in candidate.json()[0]
    assert "questions_doc_url" not in candidate.json()[0]

    unbooked = client.get("/interviews/me", headers={"X-User-Id": "c4"})
    assert unbooked.status_code == 200
    assert unbooked.json()[0]["status"] == "not_scheduled"
    assert "questions_doc_url" not in unbooked.json()[0]

    interviewer = client.get("/interviews/me", headers={"X-User-Id": "i1"})
    assert interviewer.status_code == 200
    assert len(interviewer.json()) == 2
    assert interviewer.json()[0]["candidate_name"] == "Alex"
    assert interviewer.json()[0]["rubric_url"] == "https://example.com/interview-rubric"
    assert interviewer.json()[0]["questions_doc_url"] == "https://example.com/interview-questions"
    assert client.get("/interviews/me", headers={"X-User-Id": "admin"}).status_code == 403


def test_loads_come_from_reader_not_recomputed():
    """Admin load must mirror Person 2's interviewer_loads(), not our own count."""

    class Reader(outtake.FixtureBookingReader):
        def interviewer_loads(self):
            return {"i1": 7, "i-new": 1}

    outtake.configure_booking_reader(Reader())
    loads = {l.id: l.load for l in outtake.get_admin_overview().interviewer_loads}
    assert loads["i1"] == 7
    assert loads["i2"] == 0
    assert loads["i-new"] == 1  # unknown-to-us interviewer still reported


def test_bookings_with_unknown_users_do_not_crash():
    """Person 2's bookings may reference users our user source doesn't know yet."""

    start = datetime(2026, 12, 1, 15, tzinfo=UTC)

    class Reader(outtake.FixtureBookingReader):
        def list_bookings(self):
            return [
                Booking(
                    id="b-x",
                    candidate_id="c-unknown",
                    start=start,
                    end=start.replace(minute=30),
                    interviewer_ids=["i1", "i-unknown"],
                )
            ]

    outtake.configure_booking_reader(Reader())
    booking = outtake.get_admin_overview().bookings[0]
    assert booking.candidate_name == "c-unknown"
    assert [m.name for m in booking.interviewers] == ["Ana", "i-unknown"]


def test_prefers_person1_load_inputs_when_available(monkeypatch):
    """When Person 1's repository module lands, its users/config win over fixtures."""

    monkeypatch.undo()  # drop the autouse _live_inputs override for this test
    config = Config(
        slot_length_min=30,
        interview_dates=[date(2026, 12, 1)],
        timezone="America/New_York",
        interviewers_per_interview=1,
        min_candidate_slots=1,
        questions_doc_url="https://example.com/live-questions",
    )
    users = [User(id="live-c", name="Live", email="l@example.com", role=Role.CANDIDATE)]
    fake = types.ModuleType("app.scheduling.repository")
    fake.load_inputs = lambda: (config, users, [], [])
    monkeypatch.setitem(sys.modules, "app.scheduling.repository", fake)

    loaded_users, loaded_config = outtake.load_context()
    assert [u.id for u in loaded_users] == ["live-c"]
    assert outtake.config_value(loaded_config, "questions_doc_url") == (
        "https://example.com/live-questions"
    )


def test_default_reader_uses_person2_module_when_present(monkeypatch):
    start = datetime(2026, 12, 1, 15, tzinfo=UTC)
    booking = Booking(
        id="p2", candidate_id="c3", start=start, end=start.replace(minute=30), interviewer_ids=["i3"]
    )
    fake = types.ModuleType("app.scheduling.bookings")
    fake.list_bookings = lambda: [booking]
    fake.bookings_for_user = lambda user_id: [booking] if user_id in ("c3", "i3") else []
    fake.interviewer_loads = lambda: {"i3": 1}
    monkeypatch.setitem(sys.modules, "app.scheduling.bookings", fake)
    outtake.configure_booking_reader(None)

    assert [b.id for b in outtake.get_admin_overview().bookings] == ["p2"]
    assert "c3" not in {c.id for c in outtake.list_unbooked_candidates()}

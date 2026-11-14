"""Tests for the app wiring in ``app.main``: /health, /me and CORS."""

from app.auth import INTERVIEWER, CurrentUser, get_current_user
from app.main import app
from tests.conftest import bearer

# --- /health ---------------------------------------------------------------------


def test_health_is_public(client):
    """/health needs no sign-in."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- /me -------------------------------------------------------------------------


def test_me_without_token_is_401(client):
    """No Authorization header -> 401 with a Bearer challenge."""
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_non_bearer_scheme_is_401(client):
    """Only "Bearer <token>" is accepted."""
    response = client.get("/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401


def test_me_returns_candidate_by_default(client, make_token):
    """A brand-new user (not on the interviewer list) is a candidate."""
    response = client.get("/me", headers=bearer(make_token(sub="new-user")))
    assert response.status_code == 200
    assert response.json() == {
        "id": "new-user",
        "email": "student@rice.edu",
        "role": "candidate",
    }


def test_me_returns_role_from_database(client, make_token, fake_db):
    """The role comes from the interviewers table."""
    fake_db.roles["user-1"] = INTERVIEWER
    response = client.get("/me", headers=bearer(make_token()))
    assert response.json()["role"] == INTERVIEWER


def test_dependency_override_example(client):
    """How to test a protected route WITHOUT tokens, for future routers.

    ``app.dependency_overrides`` swaps ``get_current_user`` for a function
    returning whatever user you need. The ``client`` fixture clears overrides
    after each test.
    """
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="board-1", email="board@rice.edu", role="board"
    )
    response = client.get("/me")  # note: no Authorization header
    assert response.json()["role"] == "board"


# --- CORS --------------------------------------------------------------------------


def test_cors_allows_frontend_origin_with_authorization_header(client):
    """The browser's preflight from the Next.js app is approved."""
    response = client.options(
        "/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_rejects_other_origins(client):
    """Other websites can't call the API from a user's browser."""
    response = client.options(
        "/me",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers

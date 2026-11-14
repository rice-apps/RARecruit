"""Tests for ``app.auth``: token verification, role lookup and role checks.

Supabase is faked (see ``conftest.py``), so these run offline.
"""

import time
from typing import Annotated

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import auth
from app.auth import BOARD, CANDIDATE, INTERVIEWER, CurrentUser, require_role
from tests.conftest import bearer

# --- verify_token -------------------------------------------------------------


def test_valid_token_returns_claims(make_token):
    """A correctly signed, unexpired token for our project is accepted."""
    claims = auth.verify_token(make_token(sub="abc"))
    assert claims["sub"] == "abc"
    assert claims["email"] == "student@rice.edu"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"exp": int(time.time()) - 60}, id="expired"),
        pytest.param({"aud": "anon"}, id="wrong-audience"),
        pytest.param({"iss": "https://other.supabase.co/auth/v1"}, id="other-project"),
        pytest.param({"drop": ["sub"]}, id="missing-sub"),
        pytest.param({"drop": ["exp"]}, id="missing-exp"),
        pytest.param(
            {"key": ec.generate_private_key(ec.SECP256R1())}, id="forged-signature"
        ),
        # "Algorithm confusion": HS256 must never be accepted, even if signed.
        pytest.param(
            {"key": "a-shared-secret-at-least-32-bytes!!", "algorithm": "HS256"},
            id="hs256",
        ),
    ],
)
def test_bad_tokens_are_rejected_with_401(make_token, overrides):
    """Each kind of invalid token raises 401, without saying exactly why."""
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_token(make_token(**overrides))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


def test_garbage_token_is_rejected_with_401():
    """A string that isn't a JWT at all raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_token("not-a-jwt")
    assert exc_info.value.status_code == 401


def test_supabase_unreachable_gives_503_not_401(make_token, fake_jwks):
    """If we can't fetch Supabase's keys, it's our outage, not a bad token."""
    fake_jwks.error = jwt.PyJWKClientConnectionError("connection refused")
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_token(make_token())
    assert exc_info.value.status_code == 503


# --- lookup_role ----------------------------------------------------------------


def test_user_not_on_interviewer_list_is_candidate(fake_db):
    """Anyone not in the interviewers table defaults to candidate."""
    assert auth.lookup_role("someone-new") == CANDIDATE
    assert fake_db.queried_tables == ["interviewers"]


@pytest.mark.parametrize("role", [INTERVIEWER, BOARD])
def test_listed_roles_are_returned(fake_db, role):
    """Interviewer/board rows return that role."""
    fake_db.roles["user-1"] = role
    assert auth.lookup_role("user-1") == role


@pytest.mark.parametrize("bad_value", ["admin", "Interviewer", "", None])
def test_unknown_role_values_fall_back_to_candidate(fake_db, bad_value):
    """Typos or unexpected DB values never grant extra access."""
    fake_db.roles["user-1"] = bad_value
    assert auth.lookup_role("user-1") == CANDIDATE


# --- require_role -----------------------------------------------------------------


def test_require_role_rejects_unknown_role_names():
    """A typo in a route's allowed roles fails loudly at startup."""
    with pytest.raises(ValueError, match="interviwer"):
        require_role("interviwer")


@pytest.fixture
def protected_client():
    """A tiny app with one interviewer/board-only route, for role tests.

    Yields:
        A TestClient whose ``GET /staff-only`` requires interviewer or board.
    """
    test_app = FastAPI()

    @test_app.get("/staff-only")
    def staff_only(
        user: Annotated[CurrentUser, Depends(require_role(INTERVIEWER, BOARD))],
    ) -> dict[str, str]:
        """Return the caller's role if they're allowed in."""
        return {"role": user.role}

    with TestClient(test_app) as test_client:
        yield test_client


def test_candidate_is_forbidden(protected_client, make_token):
    """Signed-in but wrong role -> 403 (not 401)."""
    response = protected_client.get("/staff-only", headers=bearer(make_token()))
    assert response.status_code == 403


@pytest.mark.parametrize("role", [INTERVIEWER, BOARD])
def test_allowed_roles_get_in(protected_client, make_token, fake_db, role):
    """Interviewers and board members can reach the route."""
    fake_db.roles["user-1"] = role
    response = protected_client.get("/staff-only", headers=bearer(make_token()))
    assert response.status_code == 200
    assert response.json() == {"role": role}


def test_role_claim_in_token_is_ignored(protected_client, make_token):
    """A token claiming role "board" doesn't matter: the DB decides."""
    token = make_token(role="board", app_role="board")
    response = protected_client.get("/staff-only", headers=bearer(token))
    assert response.status_code == 403


def test_removing_an_interviewer_takes_effect_on_next_request(
    protected_client, make_token, fake_db
):
    """Roles are re-read every request, so the same token loses access."""
    token = make_token()
    fake_db.roles["user-1"] = INTERVIEWER
    assert protected_client.get("/staff-only", headers=bearer(token)).status_code == 200

    del fake_db.roles["user-1"]  # removed from the interviewer list
    assert protected_client.get("/staff-only", headers=bearer(token)).status_code == 403


def test_missing_token_is_401_before_role_check(protected_client):
    """Not signed in at all -> 401, not 403."""
    assert protected_client.get("/staff-only").status_code == 401

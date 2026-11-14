"""Shared pytest setup: fake env vars, fake Supabase, and token helpers.

Nothing here talks to a real Supabase project:
    * Env vars are set to dummy values BEFORE the app is imported, so a
      developer's real ``backend/.env`` is never used by tests.
    * Supabase's public signing keys (JWKS) are replaced by a key pair we
      generate here, so we can mint valid (and deliberately invalid) tokens.
    * The database is replaced by ``FakeSupabase``, an in-memory stand-in.

Fixtures (use them by adding the name as a test function argument):
    make_token  -- build a signed Supabase-style access token
    fake_db     -- set users' roles: ``fake_db.roles["user-id"] = "interviewer"``
    client      -- a TestClient for the real app (``app.main.app``)
"""

import os

# Must run before any `import app...`: app.config reads env vars at import time.
# Real environment variables override backend/.env, so these always win.
os.environ["SUPABASE_URL"] = "https://test-project.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"

# All imports below intentionally come AFTER the env setup above.
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.main import app

SUPABASE_URL = os.environ["SUPABASE_URL"]
ISSUER = f"{SUPABASE_URL}/auth/v1"

# One ES256 key pair for the whole test run: plays the role of Supabase's key.
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeJWKSClient:
    """Stands in for ``jwt.PyJWKClient``: always returns our test public key.

    Set ``error`` to an exception instance to simulate a JWKS failure
    (e.g. Supabase unreachable).
    """

    def __init__(self, public_key):
        """Store the public key to hand back.

        Args:
            public_key: The key used to verify token signatures.
        """
        self.public_key = public_key
        self.error: Exception | None = None

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        """Mimic PyJWKClient: return an object with a ``.key`` attribute.

        Args:
            token: The JWT (ignored; there's only one key).

        Returns:
            An object whose ``.key`` is the test public key.

        Raises:
            Exception: Whatever ``self.error`` is set to, if set.
        """
        if self.error is not None:
            raise self.error
        return SimpleNamespace(key=self.public_key)


class FakeQuery:
    """Mimics the supabase query builder chain used by ``auth.lookup_role``:
    ``table(...).select(...).eq(col, value).limit(n).execute().data``.
    """

    def __init__(self, db: "FakeSupabase", table: str):
        """Start a query on ``table``.

        Args:
            db: The fake database holding the rows.
            table: Table name being queried.
        """
        self.db = db
        self.table = table
        self.filters: dict[str, str] = {}

    def select(self, *_columns: str) -> "FakeQuery":
        """No-op: the fake always returns the ``role`` column."""
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        """Record an equality filter.

        Args:
            column: Column name (we expect "id").
            value: Value it must equal.
        """
        self.filters[column] = value
        return self

    def limit(self, _n: int) -> "FakeQuery":
        """No-op: at most one row per user exists in the fake."""
        return self

    def execute(self) -> SimpleNamespace:
        """Run the query against ``db.roles``.

        Returns:
            An object with ``.data``: ``[{"role": ...}]`` or ``[]``.
        """
        self.db.queried_tables.append(self.table)
        user_id = self.filters.get("id")
        if self.table == "interviewers" and user_id in self.db.roles:
            return SimpleNamespace(data=[{"role": self.db.roles[user_id]}])
        return SimpleNamespace(data=[])


class FakeSupabase:
    """In-memory stand-in for the supabase client.

    Attributes:
        roles: Maps user id -> value in the ``interviewers.role`` column.
            Users not in this dict are "not on the interviewer list".
        queried_tables: Every table name queried, to assert on in tests.
    """

    def __init__(self):
        """Start with no interviewers."""
        self.roles: dict[str, str] = {}
        self.queried_tables: list[str] = []

    def table(self, name: str) -> FakeQuery:
        """Begin a query, like ``supabase.table(name)``.

        Args:
            name: Table name.
        """
        return FakeQuery(self, name)


@pytest.fixture(autouse=True)
def fake_jwks(monkeypatch) -> FakeJWKSClient:
    """Replace Supabase's JWKS endpoint with our test key (every test).

    Returns:
        The fake, so a test can set ``fake_jwks.error`` to simulate outages.
    """
    fake = FakeJWKSClient(SIGNING_KEY.public_key())
    monkeypatch.setattr(auth, "_jwks_client", fake)
    return fake


@pytest.fixture(autouse=True)
def fake_db(monkeypatch) -> FakeSupabase:
    """Replace the real supabase client used by ``app.auth`` (every test).

    Returns:
        The fake DB; set roles with ``fake_db.roles["<user id>"] = "board"``.
    """
    fake = FakeSupabase()
    monkeypatch.setattr(auth, "supabase", fake)
    return fake


@pytest.fixture
def make_token():
    """Return a function that builds a signed Supabase-style access token.

    By default the token is valid. Pass keyword arguments to override or add
    claims, ``drop=[...]`` to remove claims, ``key=`` to sign with a different
    key, or ``algorithm=`` to sign with a different algorithm.

    Example:
        make_token(sub="user-1")                    # valid
        make_token(exp=int(time.time()) - 60)       # expired
        make_token(drop=["sub"])                    # missing "sub"
    """

    def _make(
        *,
        drop: tuple[str, ...] | list[str] = (),
        key=SIGNING_KEY,
        algorithm: str = "ES256",
        **claims,
    ) -> str:
        now = int(time.time())
        payload = {
            "sub": "user-1",
            "email": "student@rice.edu",
            "aud": "authenticated",
            "iss": ISSUER,
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",  # Supabase's Postgres role, not ours
            **claims,
        }
        for name in drop:
            payload.pop(name, None)
        return jwt.encode(payload, key, algorithm=algorithm)

    return _make


@pytest.fixture
def client():
    """A TestClient for the real app. Clears dependency overrides afterwards.

    Yields:
        ``fastapi.testclient.TestClient`` wrapping ``app.main.app``.
    """
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def bearer(token: str) -> dict[str, str]:
    """Build the Authorization header the frontend sends.

    Args:
        token: A JWT.

    Returns:
        ``{"Authorization": "Bearer <token>"}``.
    """
    return {"Authorization": f"Bearer {token}"}

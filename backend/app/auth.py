"""Authentication and role checks shared by every router.

How a request is authenticated:
    1. The Next.js frontend signs the user in with Supabase Auth (Google) and
       sends the Supabase access token as ``Authorization: Bearer <token>``.
    2. ``verify_token`` checks the token's signature, issuer, audience and expiry
       against Supabase's public signing keys (JWKS).
    3. ``get_current_user`` looks up the user's app role in Postgres on EVERY
       request, so a role change (e.g. removing an interviewer) applies at once.
    4. ``require_role`` rejects users whose role is not allowed on a route.

Usage in a router:
    # Any signed-in user (candidates included), e.g. Scheduling:
    def handler(user: Annotated[CurrentUser, Depends(get_current_user)]): ...

    # Interviewer/board-only router:
    router = APIRouter(dependencies=[Depends(require_role(INTERVIEWER, BOARD))])
"""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.db import supabase

# --- App roles ---------------------------------------------------------------
# These are OUR roles, stored in Postgres. They are unrelated to the JWT's own
# "role" claim, which is Supabase's Postgres role (always "authenticated").
CANDIDATE = "candidate"
INTERVIEWER = "interviewer"
BOARD = "board"
ROLES = frozenset({CANDIDATE, INTERVIEWER, BOARD})

# --- Token verification setup ------------------------------------------------
_SUPABASE_URL = settings.supabase_url.rstrip("/")
_ISSUER = f"{_SUPABASE_URL}/auth/v1"
_AUDIENCE = "authenticated"  # Supabase's "aud" for signed-in users
# Supabase asymmetric signing keys are ES256 (default) or RS256. HS256 is
# deliberately NOT listed: accepting it would let a shared secret sign tokens.
_ALGORITHMS = ["ES256", "RS256"]

# Fetches Supabase's public keys once and caches them, so we don't make a
# network call on every request. Unknown key IDs trigger a refetch (key rotation).
_jwks_client = jwt.PyJWKClient(f"{_ISSUER}/.well-known/jwks.json")

# auto_error=False: a missing header reaches our code (-> 401) instead of
# FastAPI's built-in error. Also makes the "Authorize" button appear in /docs.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The signed-in user making the request.

    Attributes:
        id: Supabase auth user UUID (the JWT "sub"). Use this as the stable key
            for the user everywhere, never the email.
        email: The user's email from the token (may be empty).
        role: The user's app role from Postgres, one of ``ROLES``.
    """

    id: str
    email: str
    role: str


def verify_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Args:
        token: The raw JWT from the Authorization header.

    Returns:
        The decoded claims (includes "sub", "email", "exp", ...).

    Raises:
        HTTPException: 401 if the token is malformed, forged, expired, issued by
            another project, or meant for another audience.
    """
    try:
        # Pick the public key matching the token's "kid" header.
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            audience=_AUDIENCE,
            issuer=_ISSUER,
            # Fail if these claims are missing, rather than silently accepting.
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        # Covers bad signatures, expiry, wrong iss/aud, and JWKS fetch failures
        # (PyJWKClientError subclasses PyJWTError). Don't leak details to clients.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def lookup_role(user_id: str) -> str:
    """Return the app role for a user, read fresh from Postgres.

    TODO(team): table design is not final. This assumes an ``interviewers``
    table keyed by the Supabase user id with a ``role`` column ("interviewer"
    or "board"); anyone not listed is a candidate. Keep all role storage
    details inside this function so changing the schema only touches here.

    Args:
        user_id: Supabase auth user UUID (JWT "sub").

    Returns:
        One of ``ROLES``.
    """
    res = (
        supabase.table("interviewers")
        .select("role")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return CANDIDATE  # Not on the interviewer list -> candidate.

    role = res.data[0].get("role")
    # Whitelist: an unexpected value in the DB (typo, old role name) must never
    # grant access, so fall back to the least-privileged role.
    return role if role in ROLES else CANDIDATE


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """FastAPI dependency: authenticate the request and load the user's role.

    Declared with ``def`` (not ``async def``) because the supabase client is
    synchronous; FastAPI runs it in a thread pool so it doesn't block the loop.

    Args:
        creds: Parsed ``Authorization: Bearer`` header, or None if missing.

    Returns:
        The authenticated ``CurrentUser``.

    Raises:
        HTTPException: 401 if the header is missing or the token is invalid.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = verify_token(creds.credentials)
    user_id = claims["sub"]  # guaranteed present by verify_token's "require"

    return CurrentUser(
        id=user_id,
        email=claims.get("email", ""),
        role=lookup_role(user_id),  # never trust a role from the token/client
    )


def require_role(*allowed: str):
    """Build a dependency that only lets users with one of ``allowed`` roles in.

    Args:
        *allowed: Role names permitted on the route, e.g. ``INTERVIEWER, BOARD``.

    Returns:
        A FastAPI dependency that returns the ``CurrentUser`` if permitted.

    Raises:
        ValueError: At import time, if an unknown role name is passed (catches
            typos like ``require_role("interviwer")`` before they ship).
    """
    unknown = set(allowed) - ROLES
    if unknown:
        raise ValueError(f"Unknown role(s) in require_role: {sorted(unknown)}")

    def checker(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        """Return the user if their role is allowed, else raise 403.

        Args:
            user: The authenticated user (from ``get_current_user``).

        Returns:
            The same ``CurrentUser``, so routes can use it directly.

        Raises:
            HTTPException: 403 if the user's role is not in ``allowed``.
        """
        if user.role not in allowed:
            # 403 (not 401): we know who they are, they just can't do this.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this resource",
            )
        return user

    return checker

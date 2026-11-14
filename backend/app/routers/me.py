"""``GET /me``: who is signed in, and what role they have.

The frontend calls this right after Supabase sign-in to decide which pages to
show (candidate pages vs. interviewer pages). This only affects what the UI
displays; it is NOT what keeps candidates out of interviewer data. Every
protected route checks the role again on the backend (see ``app.auth``).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user

# tags=["auth"] groups this endpoint under "auth" in the /docs page.
router = APIRouter(tags=["auth"])


class MeResponse(BaseModel):
    """Response body for ``GET /me``.

    Attributes:
        id: Supabase auth user UUID.
        email: The user's email address.
        role: App role: "candidate", "interviewer" or "board".
    """

    id: str
    email: str
    role: str


@router.get("/me")
def read_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    """Return the signed-in user's id, email and app role.

    Args:
        user: Injected by ``get_current_user``. The request is rejected with
            401 before this runs if the token is missing or invalid.

    Returns:
        The user's id, email and role (role read fresh from the database).
    """
    return MeResponse(id=user.id, email=user.email, role=user.role)

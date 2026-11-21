"""Person 3 outtake routes: admin booking views, CSV export, and /interviews/me.

Read-only. Booking writes (POST /bookings, DELETE /bookings/{id}) live in
Person 2's router; config/availability live in Person 1's.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.scheduling.models import Role, User
from app.scheduling.outtake import (
    AdminBookingOverview,
    InterviewerMyInterview,
    MyInterview,
    get_admin_overview,
    get_user,
    list_my_interviews,
)

router = APIRouter()


def _current_user(x_user_id: str | None) -> User | None:
    # Single swap point: replace with Person 1's role/auth dependency once it
    # exists (spec §2 derives roles from config email lists).
    return get_user(x_user_id or "")


def _require_admin(x_user_id: str | None) -> None:
    user = _current_user(x_user_id)
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="admin role required")


@router.get("/admin/bookings", response_model=AdminBookingOverview)
def get_admin_bookings(
    x_user_id: str | None = Header(default=None),
) -> AdminBookingOverview:
    _require_admin(x_user_id)
    return get_admin_overview()


@router.get("/admin/overview", response_model=AdminBookingOverview)
def get_booking_overview(
    x_user_id: str | None = Header(default=None),
) -> AdminBookingOverview:
    _require_admin(x_user_id)
    return get_admin_overview()


@router.get("/admin/bookings.csv")
def export_bookings_csv(
    x_user_id: str | None = Header(default=None),
) -> StreamingResponse:
    _require_admin(x_user_id)
    overview = get_admin_overview()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "booking_id",
        "candidate_id",
        "candidate_name",
        "start",
        "end",
        "timezone",
        "status",
        "interviewers",
        "location",
    ])
    for booking in overview.bookings:
        writer.writerow([
            booking.id,
            booking.candidate_id,
            booking.candidate_name,
            booking.start.isoformat(),
            booking.end.isoformat(),
            booking.timezone,
            booking.status.value,
            "; ".join(member.name for member in booking.interviewers),
            booking.location or "",
        ])

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bookings.csv"'},
    )


@router.get(
    "/interviews/me",
    response_model=list[MyInterview | InterviewerMyInterview],
)
def get_my_interviews(
    x_user_id: str | None = Header(default=None),
) -> list[MyInterview | InterviewerMyInterview]:
    user = _current_user(x_user_id)
    if user is None or user.role not in (Role.INTERVIEWER, Role.CANDIDATE):
        raise HTTPException(status_code=403, detail="insufficient role")
    return list_my_interviews(user)

"""Booking-event notifications (Person 3).

Contract for Person 2: call ``notify_booking_event(event)`` after a booking
write has been persisted and outside the booking lock. This function never
raises; every problem is reported in the returned ``NotificationResult`` so a
notification failure can't roll back or 500 a successful booking.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.scheduling.models import BookingEvent, BookingStatus, User
from app.scheduling.outtake import config_value, load_context

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    """Per-call delivery counts. ``written`` counts dry-run outbox files."""

    sent: int = 0
    written: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass
class _Recipient:
    user: User
    subject: str
    body: str


_CANDIDATE_SUBJECTS = {
    "booked": "Your RARecruit interview is booked",
    "cancelled": "Your RARecruit interview has been cancelled",
    "rescheduled": "Your RARecruit interview has been rescheduled",
}
_INTERVIEWER_SUBJECTS = {
    "booked": "A new RARecruit interview is assigned",
    "cancelled": "An RARecruit interview assignment has been cancelled",
    "rescheduled": "An RARecruit interview assignment has changed",
}


def _dry_run_enabled() -> bool:
    """Only an explicit, case-insensitive ``false`` enables live sending."""
    raw_value = os.getenv("EMAIL_DRY_RUN")
    dry_run = raw_value is None or raw_value.strip().lower() != "false"
    logger.info("Email notification mode: %s", "dry-run" if dry_run else "live")
    return dry_run


_dry_run_enabled()


def _when(start: datetime, end: datetime, timezone: ZoneInfo) -> str:
    start, end = start.astimezone(timezone), end.astimezone(timezone)
    return (
        f"{start.strftime('%A, %B %-d, %Y')} from {start.strftime('%-I:%M %p')} "
        f"to {end.strftime('%-I:%M %p %Z')}"
    )


def _recipients(
    event: BookingEvent, users: list[User], timezone: ZoneInfo
) -> list[_Recipient]:
    booking = event.booking
    users_by_id = {user.id: user for user in users}
    when = _when(booking.start, booking.end, timezone)
    location = f"\nLocation: {booking.location}" if booking.location else ""
    recipients: list[_Recipient] = []

    candidate = users_by_id.get(booking.candidate_id)
    if candidate is not None:
        subject = _CANDIDATE_SUBJECTS[event.event_type]
        recipients.append(
            _Recipient(
                user=candidate,
                subject=subject,
                body=f"Hi {candidate.name},\n\n{subject}: {when}.{location}\n",
            )
        )
    else:
        logger.warning("Unknown candidate %s for booking %s", booking.candidate_id, booking.id)

    candidate_name = candidate.name if candidate else booking.candidate_id
    for interviewer_id in booking.interviewer_ids:
        interviewer = users_by_id.get(interviewer_id)
        if interviewer is None:
            logger.warning("Unknown interviewer %s for booking %s", interviewer_id, booking.id)
            continue
        subject = _INTERVIEWER_SUBJECTS[event.event_type]
        recipients.append(
            _Recipient(
                user=interviewer,
                subject=subject,
                body=f"Hi {interviewer.name},\n\n{subject}: {candidate_name}, {when}.{location}\n",
            )
        )

    # Reschedule (spec §11 / work-split): interviewers dropped from the old
    # panel get a cancellation for their old assignment.
    previous = event.previous_booking
    if event.event_type == "rescheduled" and previous is not None:
        old_when = _when(previous.start, previous.end, timezone)
        subject = _INTERVIEWER_SUBJECTS["cancelled"]
        for interviewer_id in previous.interviewer_ids:
            if interviewer_id in booking.interviewer_ids:
                continue
            interviewer = users_by_id.get(interviewer_id)
            if interviewer is None:
                continue
            recipients.append(
                _Recipient(
                    user=interviewer,
                    subject=subject,
                    body=f"Hi {interviewer.name},\n\n{subject}: {candidate_name}, {old_when}.\n",
                )
            )
    return recipients


def _message(recipient: _Recipient) -> EmailMessage:
    message = EmailMessage()
    message["To"] = recipient.user.email
    message["Subject"] = recipient.subject
    message.set_content(recipient.body)
    return message


def _write_marker(path: Path, delivered: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as marker:
            json.dump(sorted(delivered), marker, indent=2)
            marker.flush()
            os.fsync(marker.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _load_marker(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read notification marker %s: %s", path, exc)
        return set()
    if not isinstance(values, list):
        logger.warning("Notification marker %s is not a list", path)
        return set()
    return {value for value in values if isinstance(value, str)}


def _deliver(key: str, recipients: list[_Recipient], result: NotificationResult) -> None:
    """Send (or dry-run write) once per recipient per ``key``; idempotent."""
    outbox = Path("backend/data/outbox")
    marker_path = outbox / f"{key}.sent.json"
    delivered = _load_marker(marker_path)
    pending: list[tuple[str, _Recipient, EmailMessage]] = []
    for recipient in recipients:
        if recipient.user.id in delivered:
            continue
        if not recipient.user.email:
            logger.warning("Skipping user %s without an email for %s", recipient.user.id, key)
            result.skipped += 1
            continue
        pending.append((recipient.user.id, recipient, _message(recipient)))

    if _dry_run_enabled():
        for recipient_id, recipient, message in pending:
            try:
                outbox.mkdir(parents=True, exist_ok=True)
                path = outbox / f"{key}-{recipient_id}-{uuid.uuid4().hex}.eml"
                path.write_bytes(message.as_bytes())
                delivered.add(recipient_id)
                _write_marker(marker_path, delivered)
                result.written += 1
            except OSError as exc:
                result.failures.append(f"{recipient.user.email}: {exc}")
        return

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not all((refresh_token, client_id, client_secret)):
        result.failures.append(
            "GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, and GOOGLE_CLIENT_SECRET "
            "are required when EMAIL_DRY_RUN is false"
        )
        return
    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=[os.getenv("GOOGLE_GMAIL_SCOPE", "https://www.googleapis.com/auth/gmail.send")],
        )
        service = build("gmail", "v1", credentials=credentials)
    except (HttpError, OSError, RefreshError, RuntimeError, ValueError) as exc:
        result.failures.append(str(exc))
        return

    for recipient_id, recipient, message in pending:
        try:
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            delivered.add(recipient_id)
            _write_marker(marker_path, delivered)
            result.sent += 1
        except (HttpError, OSError, RefreshError, RuntimeError, ValueError) as exc:
            result.failures.append(f"{recipient.user.email}: {exc}")


def notify_booking_event(
    event: BookingEvent, users: list[User] | None = None
) -> NotificationResult:
    """Notify the candidate and each panel interviewer about one booking event.

    ``users`` is optional: Person 2 can pass just the event and names/emails
    are read from Person 1's data. Never raises.
    """
    result = NotificationResult()
    try:
        if event.event_type == "booked" and event.booking.status != BookingStatus.CONFIRMED:
            return result
        context_users, config = load_context()
        timezone = ZoneInfo(config_value(config, "timezone") or "UTC")
        recipients = _recipients(event, users if users is not None else context_users, timezone)
        _deliver(event.event_id, recipients, result)
    except Exception as exc:  # noqa: BLE001 - must not break the booking path
        logger.exception("Booking notification failed for event %s", event.event_id)
        result.failures.append(f"notification error: {exc}")
    return result


__all__ = ["NotificationResult", "notify_booking_event"]

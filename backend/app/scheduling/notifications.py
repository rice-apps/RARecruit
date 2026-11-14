"""Candidate and interviewer publication notifications."""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.scheduling.models import (
    Interview,
    JsonRepository,
    NotFoundError,
    ScheduleRun,
    User,
)

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    """Outcome of attempting publication notifications."""

    sent: int = 0
    written: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass
class _Recipient:
    user: User
    subject: str
    body: str


def _dry_run_enabled() -> bool:
    """Only an explicit, case-insensitive ``false`` enables live sending."""
    raw_value = os.getenv("EMAIL_DRY_RUN")
    dry_run = raw_value is None or raw_value.strip().lower() != "false"
    logger.info("Email notification mode: %s", "dry-run" if dry_run else "live")
    return dry_run


_dry_run_enabled()


def _format_interview(
    interview: Interview,
    users_by_id: dict[str, User],
    timezone: ZoneInfo,
) -> str:
    start = interview.start.astimezone(timezone)
    end = interview.end.astimezone(timezone)
    duration = int((interview.end - interview.start).total_seconds() // 60)
    panel = ", ".join(
        users_by_id[interviewer_id].name
        for interviewer_id in interview.interviewer_ids
        if interviewer_id in users_by_id
    )
    return (
        f"{start.strftime('%A, %B %-d, %Y')} from {start.strftime('%-I:%M %p')} "
        f"to {end.strftime('%-I:%M %p %Z')} ({duration} minutes); "
        f"panel: {panel or 'not available'}"
    )


def _recipients(
    run: ScheduleRun,
    users: list[User],
    timezone: ZoneInfo,
) -> list[_Recipient]:
    users_by_id = {user.id: user for user in users}
    recipients: list[_Recipient] = []
    interviewer_interviews: dict[str, list[Interview]] = {}

    for interview in run.interviews:
        candidate = users_by_id.get(interview.candidate_id)
        if candidate is not None:
            recipients.append(
                _Recipient(
                    user=candidate,
                    subject="Your RARecruit interview",
                    body=(
                        f"Hi {candidate.name},\n\n"
                        "Your RARecruit interview is scheduled for:\n"
                        f"{_format_interview(interview, users_by_id, timezone)}\n"
                    ),
                )
            )
        for interviewer_id in interview.interviewer_ids:
            interviewer_interviews.setdefault(interviewer_id, []).append(interview)

    for interviewer_id, interviews in interviewer_interviews.items():
        interviewer = users_by_id.get(interviewer_id)
        if interviewer is None:
            logger.warning("Skipping unknown interviewer %s for run %s", interviewer_id, run.id)
            continue
        details = "\n".join(
            f"- {users_by_id[interview.candidate_id].name if interview.candidate_id in users_by_id else interview.candidate_id}: "
            f"{_format_interview(interview, users_by_id, timezone)}"
            for interview in interviews
        )
        recipients.append(
            _Recipient(
                user=interviewer,
                subject="Your RARecruit interview assignments",
                body=f"Hi {interviewer.name},\n\nYour interview assignments:\n{details}\n",
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
    fd, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.stem}.",
        suffix=".tmp",
    )
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


def notify(run: ScheduleRun, users: list[User]) -> NotificationResult:
    """Notify scheduled users; unscheduled candidates receive no email."""
    result = NotificationResult()
    try:
        config = JsonRepository().load_config()
        timezone = ZoneInfo(config.timezone)
    except (NotFoundError, OSError, ValueError) as exc:
        result.failures.append(f"could not load notification timezone: {exc}")
        return result

    outbox = Path("backend/data/outbox")
    marker_path = outbox / f"{run.id}.sent.json"
    delivered = _load_marker(marker_path)
    recipients = _recipients(run, users, timezone)
    pending: list[tuple[str, _Recipient, EmailMessage]] = []
    for recipient in recipients:
        if recipient.user.id in delivered:
            continue
        if not recipient.user.email:
            logger.warning("Skipping user %s without an email for run %s", recipient.user.id, run.id)
            result.skipped += 1
            continue
        pending.append((recipient.user.id, recipient, _message(recipient)))

    if _dry_run_enabled():
        for recipient_id, recipient, message in pending:
            try:
                outbox.mkdir(parents=True, exist_ok=True)
                path = outbox / f"{run.id}-{recipient_id}-{uuid.uuid4().hex}.eml"
                path.write_bytes(message.as_bytes())
                delivered.add(recipient_id)
                _write_marker(marker_path, delivered)
                result.written += 1
            except OSError as exc:
                result.failures.append(f"{recipient.user.email}: {exc}")
        return result

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
        return result
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
        return result

    for recipient_id, recipient, message in pending:
        try:
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            delivered.add(recipient_id)
            _write_marker(marker_path, delivered)
            result.sent += 1
        except (HttpError, OSError, RefreshError, RuntimeError, ValueError) as exc:
            result.failures.append(f"{recipient.user.email}: {exc}")
    return result


__all__ = ["NotificationResult", "notify"]

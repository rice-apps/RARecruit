# Interview Scheduling Spec

## 1. Overview

The scheduling platform uses a Calendly-style booking model. Interviewers publish
fixed availability slots, candidates view eligible open slots, and candidates
book a slot themselves. The system does not use a solver or create/publish
schedule runs.

The current implementation also includes a fixture-backed frontend/demo mode,
which allows outtake pages to work before Person 1 or Person 2 live data is
available. Fixtures are development fallbacks, not the production source of
truth.

## 2. Roles

| Role | Can do |
|---|---|
| Admin | Edit public/private config, view all bookings, view unbooked candidates and interviewer load, and book on a candidate's behalf when enabled. |
| Interviewer | Submit fixed availability slots and recusals; view assigned bookings and interviewer-only materials. |
| Candidate | View eligible slots and book, cancel, or reschedule according to the rules in force. |

Roles are derived from email lists in configuration: an admin list takes
precedence, then the interviewer list, and every remaining authenticated
account is a candidate. A candidate allowlist or domain restriction may be
added later.

## 3. Phases

The scheduling cycle moves through:

1. `setup`
2. `interviewer_availability`
3. `booking`
4. `closed`

The implementation may keep interviewer availability open during `booking`.
Candidates may only write bookings while the phase is `booking`.

## 4. Config

Set by an admin during `setup`.

| Field | Meaning |
|---|---|
| `interview_dates` | Dates on which interviews may happen. |
| `slot_length_min` | Interview length. Defaults to `30`. |
| `timezone` | IANA timezone used to display and interpret times. |
| `daily_start_time` / `daily_end_time` | Optional booking window. |
| `interviewers_per_interview` | Required panel size *k*. |
| `min_interviewer_minutes` or `min_interviewer_slots` | Minimum availability an interviewer must submit. |
| `max_interviews_per_interviewer` | Optional total interviewer load cap. |
| `max_interviews_per_interviewer_per_day` | Optional per-day interviewer load cap. |
| `interviewer_emails` | Email allowlist for interviewer role assignment. |
| `admin_emails` | Email allowlist for admin role assignment. |
| `rubric_url` | Interview rubric link. Interviewer/admin only. |
| `questions_doc_url` | Interview questions document link. Interviewer/admin only. |
| `location` or `video_link` | Optional interview location, used for views and notifications only if configured. |
| `phase` | Current lifecycle phase. |

Candidate availability and `min_candidate_minutes` are removed.

The config response must be split by role:

- Public: interview dates, slot length, timezone, daily window, and phase.
- Interviewer/admin: rubric, questions document, panel and load settings.
- Candidate responses must never contain rubric or questions document fields.

## 5. Slot Grid

Interviewers select fixed grid cells, with each cell equal to
`slot_length_min`. Interview dates and daily windows determine the grid.
Range merging, partial-overlap matching, and candidate availability ranges are
not part of the booking model.

An interviewer should meet the minimum grid-cell count or minutes before
availability is considered complete.

## 6. Booking Rules

A slot is visible to a candidate only when all of the following are true:

1. At least *k* interviewers offered the slot.
2. Enough eligible interviewers remain free in that slot.
3. Enough have no recusal with the candidate.
4. Enough are below their total and per-day load caps.
5. The candidate has not already booked.

At booking time, the system selects the eligible panel by least-loaded
interviewer, then stable tie-breaking. This preserves load balancing without an
optimization solver.

The panel selection and all availability checks happen in the booking
transaction. A booking must re-check eligibility under the write lock.

## 7. Concurrency and Integrity

Two candidates may book the same slot concurrently. JSON and Postgres
implementations must provide process-safe serialization and a final availability
re-check.

- JSON: a process-level lock plus an atomic booking write and availability
  re-check.
- Postgres: the corresponding database constraints and transaction locking.
- A losing write returns `409 Conflict` with a "slot just taken" response.
- Once confirmed, removing an interviewer from availability is blocked unless
  an admin reassigns or replaces the booking.

## 8. Core Entities

| Entity | Fields | Notes |
|---|---|---|
| `User` | `id`, `name`, `email`, `role` | Role may be derived from configured email lists. |
| `Config` | see §4 | Public and private fields must use role-aware views. |
| `Availability` | `interviewer_id`, `slot_start`, `slot_end` | Fixed interviewer grid slots. |
| `Recusal` | `interviewer_id`, `candidate_id`, `reason` | Unique per interviewer/candidate pair. |
| `Booking` | `id`, `candidate_id`, `start`, `end`, `interviewer_ids`, `status`, `created_at`, `location` | Replaces `ScheduleRun` and `Interview` assignments. |
| `BookingEvent` | `event_id`, `event_type`, `booking`, `previous_booking` | Used for notifications and optional calendar events. |
| `Violation` | `code`, `message`, `severity` | Booking and admin errors. |

`ScheduleRun`, draft runs, run editing, and `published` status are removed.

## 9. APIs

The caller is currently identified by `X-User-Id`; later authentication is
JWT/Supabase based.

| Method | Endpoint | Role | Description |
|---|---|---|---|
| `GET /slots/open` | Candidate | Eligible open slots for the current candidate. |
| `POST /bookings` | Candidate/admin | Create a booking. Admins may pass `candidate_id`. |
| `DELETE /bookings/{id}` | Candidate/admin | Cancel or reschedule a booking according to policy. |
| `GET /bookings` | Person 2 only if exposing a shared read; avoid conflict with collection writes. | Live booking records. |
| `GET /admin/bookings` | Admin | All bookings for the admin overview. |
| `GET /admin/overview` | Admin | Unbooked candidates and interviewer load. |
| `GET /interviews/me` | Candidate/interviewer | Role-filtered bookings. Candidates receive no private rubric/questions fields. |
| `GET /admin/bookings.csv` | Admin | CSV export. |

Person 2 owns booking writes and live booking read functions. Person 3 owns
outtake views and notifications, and must use those read functions rather than
counting load or reading storage independently.

## 10. Person 2 Integration Contract

Person 3 depends on these functions, exposed by Person 2 in `app/scheduling/bookings.py`:

```python
def list_bookings() -> list[Booking]: ...
def bookings_for_user(user_id: str) -> list[Booking]: ...
def interviewer_loads() -> dict[str, int]: ...
```

Those functions may initially be fixture-backed. A `BookingReader` adapter lets
Person 3 switch to Person 2's live implementation without changing routes or
frontend DTOs.

## 11. Notifications

Person 2 calls the Person 3 notification function only after a booking write is
saved and outside the write lock:

```python
def notify_booking_event(event: BookingEvent) -> NotificationResult: ...
```

Notification failures do not undo a successful booking. Candidate and assigned
interviewers receive booking and cancellation/reschedule events. Admin booking
on behalf of a candidate uses the same event path.

`EMAIL_DRY_RUN=true` is the default. Dry-run delivery writes readable `.eml`
files under `backend/data/outbox/`. Live Gmail delivery remains separate.
Notification results retain sent, written, skipped, and failed counts.

Events must be idempotent. A repeated event must not send duplicate messages.

## 12. Person 3 Outtake and Frontend

Person 3 owns:

- `GET /admin/bookings` and `GET /admin/overview`
- `GET /interviews/me`
- CSV export
- Booking/cancellation notifications
- `/admin/bookings` frontend
- `/me` frontend

The `/me` response has role-specific forms:

- Candidate: own booking, status, time, and optionally visible panel names.
- Interviewer: assigned candidates, time, panel, and rubric/questions links.
- Candidate: never returns rubric or questions document fields.

The unbooked-candidate list only includes users known to or signed in through
the app unless Person 1 adds a candidate allowlist or roster.

## 13. Deferred or Unsettled

- Panel fixed at booking time versus fixed panel sign-up.
- Whether candidates see panel names before or after booking.
- Rubric-only link versus in-app scoring.
- Cancellation and reschedule cutoff policy.
- Whether interviewers may continue adding availability during booking.
- Candidate sign-in allowlist or domain restriction.
- Calendar invitations and `.ics` export.
- Location or video-link requirements.
- Booking deadline and handling for never-booked candidates.
- Postgres/Supabase persistence and real authentication.

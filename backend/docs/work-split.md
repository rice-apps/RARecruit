# Scheduling Work Split

Who owns what in the scheduling module, and how we stay out of each other's way. Read alongside [scheduling-spec.md](scheduling-spec.md).

> **Model migration:** the platform is moving from solver runs and publishing to
> candidate self-service bookings. Person 2 owns booking rules and writes;
> Person 3 owns booking views, notifications, and export. There is no
> `ScheduleRun`, draft run, publish step, `solving` phase, or candidate
> availability submission in the target model.

| Person | Area | Name |
|---|---|---|
| 1 | Intake | _TBD_ |
| 2 | Scheduling + admin edits | _TBD_ |
| 3 | Outtake | _TBD_ |

## Ground rules

- **Shared contract:** `app/scheduling/models.py` holds every type the three areas pass between each other. Changes to it go through a PR reviewed by all three.
- **Own your folders:** only edit files you own (see below). If you need a change in someone else's file, ask or open a PR for them to review.
- **Dummy data only:** everyone works from JSON in `backend/data/`. Nobody waits on someone else's code to start.
- **Stubs first:** each person commits stub versions of their public functions (correct signature, fake return value) on day 0, so others can call them right away.
- **`main.py`:** each person adds one `include_router` line for their router. Nothing else goes there.

## Person 1: Intake

Collects and stores interviewer availability and booking-cycle configuration.

**Backend**
- Config and phase endpoints: `GET/PUT /config`, `POST /config/phase`.
- Public and interviewer/admin config views. Rubric and questions links must not appear in candidate/public config responses.
- Fixed-slot availability endpoint for interviewers: `GET/PUT /availability/me`.
- Interviewer grid with 30-minute default cells; remove candidate availability.
- Recusal endpoints: `GET/PUT /recusals/me`.
- Availability validation: dates, daily window, slot alignment, and minimum interviewer slots/minutes.
- Role checks via the `X-User-Id` stub, and phase checks on every write.
- Support interviewer/admin/candidate email lists or a candidate allowlist/domain rule.
- The JSON repository that all other code reads and writes through.

**Frontend**
- Week/grid availability picker for interviewers, limited to config dates and the daily window.
- Recusal picker for interviewers.
- Admin config and phase screen, including dates, slot length, minimum interviewer availability, rubric, and questions document.

**Provides**
```python
# app/scheduling/repository.py
def load_inputs() -> tuple[Config, list[User], list[Availability], list[Recusal]]: ...
def save_availability(user_id: str, slots: list[Availability]) -> None: ...
def save_recusals(interviewer_id: str, recusals: list[Recusal]) -> None: ...
def save_config(config: Config) -> None: ...
```

**Uses:** nothing from Person 2 or 3. Intake is fully independent.

**Dummy data:** reads and writes its own files under `data/`. Start from `testinterviewdata.json`.

**Owns**
```
app/scheduling/repository.py
app/routers/intake.py
frontend/src/app/availability/
frontend/src/app/admin/config/
```

## Person 2: Scheduling + Admin Edits

Turns interviewer availability into candidate-visible slots and owns atomic booking writes.

**Backend**
- Build the fixed slot grid from config and interviewer availability.
- Implement `open_slots(candidate_id)` and re-check every booking rule:
  panel size, remaining interviewer capacity, recusals, load caps, and prior candidate booking.
- Implement atomic `book(candidate_id, slot)` with process-level locking for JSON and database constraints/transactions for Postgres.
- Select the least-loaded eligible panel with stable tie-breaking.
- Return `409` when a slot loses a concurrent booking race.
- Implement cancellation/reschedule behavior once policy is settled.
- Implement admin booking on behalf of a candidate through the same booking path.
- Block availability removal after a booking, or require an admin reassignment path.
- Notify Person 3 through `notify_booking_event(event)` only after persistence succeeds and outside the write lock.
- Endpoints:
  - `GET /slots/open`
  - `POST /bookings`
  - `DELETE /bookings/{id}`

**Frontend**
- Candidate scheduling page showing open slots and booking status.
- Optional admin-on-behalf-of-candidate booking action embedded by Person 3.

**Provides**
```python
# app/scheduling/slots.py
def build_slots(config: Config) -> list[Slot]: ...

# app/scheduling/rules.py
def open_slots(candidate_id: str) -> list[Slot]: ...
def validate_booking(candidate_id: str, slot: Slot) -> list[Violation]: ...

# app/scheduling/bookings.py
def list_bookings() -> list[Booking]: ...
def bookings_for_user(user_id: str) -> list[Booking]: ...
def interviewer_loads() -> dict[str, int]: ...
def book(candidate_id: str, slot: Slot) -> Booking: ...
```

**Uses:** `load_inputs` and availability/recusal data from Person 1.

**Dummy data:** `testinterviewdata.json`, plus booking fixtures for:
- scarce and heavy-recusal slots
- simultaneous candidate booking attempts
- load-cap and panel-size edge cases
- canceled or reassigned bookings

**Owns**
```
app/scheduling/slots.py
app/scheduling/rules.py
app/scheduling/bookings.py
app/routers/scheduling.py
frontend/src/app/scheduling/
```

## Person 3: Outtake

Stores and presents booking outtake views, and tells people when bookings change.

**Backend**
- Remove run storage and publication responsibilities: Person 3 no longer saves, lists, loads, or publishes `ScheduleRun` records and no longer advances the `published` phase.
- Admin booking overview:
  - expose `GET /admin/bookings` for all confirmed bookings, rather than adding `GET /bookings` beside Person 2's `POST /bookings` and `DELETE /bookings/{id}`;
  - include candidate name, interview start/end, panel interviewers, timezone, and booking status;
  - add booking/candidate status details needed by the frontend.
- Candidate follow-up: `GET /admin/overview` (or another explicitly admin-only endpoint) includes candidates who have not booked. This list contains only candidates known to or who have signed in to the app; candidates who never sign in are not discoverable unless Person 1 adds an allowlisted/uploaded candidate list.
- Interviewer load: use Person 2's `interviewer_loads()` read function so the admin view reports the same load counts used by panel assignment. Person 3 does not recalculate those counts separately.
- `GET /interviews/me` for the current candidate or interviewer.
  - Candidate view: the candidate's confirmed booking and panel details, if panels are visible to candidates.
  - Return an empty or not-booked response for a candidate who has not booked.
  - Candidate responses must not include rubric or questions-doc fields, even if they appear in the interviewer/admin response. The config and response models must enforce this server-side, rather than relying on frontend hiding.
  - Interviewer view: the bookings assigned to the interviewer, including candidate, time, and interviewer-only rubric/questions-doc links.
- Read `Booking` records through Person 2's `list_bookings()`, `bookings_for_user(user_id)`, and `interviewer_loads()` integration functions; do not own or directly implement the booking write, slot eligibility, lock, or race handling.
- Booking-event notifications:
  - define the notification contract in `app/scheduling/notifications.py`, such as `notify_booking_event(event)`;
  - Person 2 calls it only after a booking is successfully saved, outside the booking lock;
  - if Person 2's admin-on-behalf-of-candidate flow uses the same booking function, it triggers the same notification path;
  - notification failures must not roll back or invalidate a successful booking;
  - send or write one confirmation/assignment message to the candidate and each assigned interviewer;
  - if rescheduling is in scope, send cancellation and replacement notifications for both the old and new assignment;
  - keep `EMAIL_DRY_RUN=true` as the default and write emails to `data/outbox/` instead of sending;
  - make notification delivery idempotent so repeated requests do not duplicate messages.
  - preserve sent, dry-run-written, skipped, and failed recipient counts in `NotificationResult`.
  - include location or video-link fields only when Person 1's config supplies them.
- Export:
  - CSV booking export is Person 3's responsibility;
  - calendar invites or `.ics` export require Person 2 to generate or trigger from booking events, because Person 2 owns booking creation and cancellation;
  - leave both export options out of the implementation unless included in the settled spec.

**Frontend**
- Replace `/admin/runs` and `/admin/runs/[id]`, along with the run-review and publish screens, with `/admin/bookings`.
- `/admin/bookings` displays all bookings in a table or calendar view.
- Include the candidate-not-booked list and interviewer load view alongside or within `/admin/bookings`.
- Admin may link to or embed Person 2's admin-on-behalf-of-candidate booking action, reusing Person 2's booking endpoint instead of duplicating booking rules or writes.
- Redesign the existing `/me` page:
  - candidates see their booked interview time and assigned panel details according to the visibility decision;
  - interviewers see their assigned candidates, times, and panel assignments;
  - show rubric and questions-doc links only in the interviewer/admin view.
- Empty states:
  - candidates who have not booked see a clear not-yet-booked state;
  - interviewers with no bookings see a clear no-interviews state.

**Provides**
```python
# app/scheduling/outtake.py
def list_unbooked_candidates() -> list[User]: ...
def get_admin_overview() -> AdminBookingOverview: ...
def list_my_interviews(user: User) -> list[MyInterview | InterviewerMyInterview]: ...

# app/scheduling/notifications.py
# `users` is optional; when omitted, names/emails come from Person 1's data.
# Never raises: failures are reported in NotificationResult.failures.
def notify_booking_event(event: BookingEvent, users: list[User] | None = None) -> NotificationResult: ...
```

**Uses:** `Booking`, `BookingEvent`, and `User` from the shared models; Person 1's repository/config/user data for names and emails. Person 2 provides `list_bookings()`, `bookings_for_user(user_id)`, and `interviewer_loads()` for live booking records and load totals. Person 3 reads those functions through a replaceable `BookingReader` adapter, so a fixture reader can run until Person 2 supplies the live implementation.

How the adapters pick a source (`app/scheduling/outtake.py`):
- Bookings: Person 2's `app/scheduling/bookings.py` as soon as it exposes all three read functions; otherwise `data/sample_bookings.json`.
- Users/config: Person 1's `app/scheduling/repository.load_inputs()` if that module exists, then the shared `JsonRepository`, then the fixture. Config fields are read by name (`timezone`, `rubric_url`, `questions_doc_url`), and a missing field falls back to `None`.
- Bookings may reference users that Person 3 hasn't loaded; those render by ID instead of failing.

**Dummy data:** hand-written booking fixtures under `data/` (including a booked candidate and an unbooked candidate), so this work does not wait for Person 2 to complete the booking flow. Users need `email` fields in the fixtures.

**Owns**
```
app/scheduling/outtake.py
app/scheduling/notifications.py
app/routers/runs.py
frontend/src/app/admin/bookings/
frontend/src/app/me/
```

## Shared

| File | Owner | Rule |
|---|---|---|
| `app/scheduling/models.py` | all | PR reviewed by all three. Include `Booking`, `BookingEvent`, and `Violation`; do not add a new run model. |
| `data/testinterviewdata.json` | all | Additive changes only; don't break others' fixtures. |
| `app/main.py` | all | One `include_router` line each. |
| `docs/scheduling-spec.md` | all | Update when the Calendly booking contract changes. |

## Day 0 (together)

1. Move `app/routers/scheduling/models.py` to `app/scheduling/models.py`; delete the stray `backend/routers/` folder.
2. Replace `ScheduleRun`/run status contracts with `Booking`, `BookingEvent`, and `Violation`; keep `email` on users.
3. Each person commits stubs for their **Provides** functions.
4. Write `data/sample_bookings.json` and fixture users/candidates/interviewers.

## Milestones

| When | Goal |
|---|---|
| End of week 1 | Interviewers submit fixed slots; candidate slots include recusal, panel, and load rules. Person 3 booking views render fixture bookings. |
| End of week 2 | Candidate/admin booking works end to end, concurrent race handling is tested, and booking/cancellation emails land in `data/outbox/` (dry run). |
| After | Real Gmail send to a test inbox; then Supabase/Postgres, auth, and optional calendar integration replace stubs. |

## Out of scope for now

- Rescheduling/cancellation policy unless explicitly settled.
- Google Calendar invites and `.ics` export unless brought into the spec.
- Rubric-based in-app scoring unless separately owned.
- Postgres/Supabase persistence and real auth.

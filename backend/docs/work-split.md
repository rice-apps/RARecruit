# Scheduling Work Split

Who owns what in the scheduling module, and how we stay out of each other's way. Read alongside [scheudling-spec.md](scheudling-spec.md).

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

Collects and stores everything that goes into the solver.

**Backend**
- Config and phase endpoints: `GET/PUT /config`, `POST /config/phase`.
- Availability endpoints for both roles: `GET/PUT /availability/me`. One code path for interviewers and candidates.
- Recusal endpoints: `GET/PUT /recusals/me`.
- Availability validation (spec §7): dates, daily window, minimum minutes. Uses only the config and the submitter's own ranges.
- Role checks via the `X-User-Id` stub, and phase checks on every write.
- The JSON repository that all other code reads and writes through.

**Frontend**
- One availability form shared by interviewers and candidates, limited to the config's dates and daily window.
- Recusal picker for interviewers.
- Admin config and phase screen.

**Provides**
```python
# app/scheduling/repository.py
def load_inputs() -> tuple[Config, list[User], list[Availability], list[Recusal]]: ...
def save_availability(user_id: str, ranges: list[Availability]) -> None: ...
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

Turns inputs into a schedule, and lets an admin fix it by hand before publishing.

**Backend**
- Slot grid (spec §6).
- A rule checker that the solver and manual edits both use: availability, recusals, panel size, no double-booking, load caps.
- The solver (spec §8) with load balancing.
- Admin edits to a **draft** run:
  - move a candidate to another slot
  - add, remove or swap an interviewer on a panel
  - unschedule a candidate
  - place an unscheduled candidate
- Edit rules:
  - **Block** recusal conflicts and double-booked interviewers.
  - **Warn** (allow with confirmation) on edits outside stated availability or over a load cap.
- Endpoints: `POST /schedule/runs` (run the solver), `PATCH /schedule/runs/{id}/interviews/{candidate_id}` (edit), `GET /schedule/runs/{id}/options/{candidate_id}` (valid slots and interviewers for an edit).

**Frontend**
- Admin edit panel for a single interview, embedded in or linked from Person 3's run-review screen.

**Provides**
```python
# app/scheduling/slots.py
def build_slots(config: Config) -> list[Slot]: ...

# app/scheduling/rules.py
def validate(run: ScheduleRun, config, availability, recusals) -> list[Violation]: ...

# app/scheduling/solver.py  (pure: no file or network I/O)
def solve(config, users, availability, recusals) -> ScheduleRun: ...

# app/scheduling/edits.py
def apply_edit(run: ScheduleRun, edit: Edit, inputs) -> tuple[ScheduleRun, list[Violation]]: ...
```

**Uses:** `load_inputs` from Person 1; `save_run` / `load_run` from Person 3.

**Dummy data:** `testinterviewdata.json`, plus harder fixtures under `data/solver/`:
- a scarce slot several candidates rely on
- heavy recusals
- a candidate who can't be scheduled
- a large random case for performance

**Owns**
```
app/scheduling/slots.py
app/scheduling/rules.py
app/scheduling/solver.py
app/scheduling/edits.py
app/routers/schedule.py
frontend/src/app/admin/runs/[id]/edit/   (or an edit component Person 3 embeds)
```

## Person 3: Outtake

Stores results, publishes them, and tells people.

**Backend**
- Run storage: save, list and load runs.
- Review and publish: `GET /schedule/runs`, `GET /schedule/runs/{id}`, `POST /schedule/runs/{id}/publish`.
- `GET /interviews/me` for interviewers and candidates.
- Gmail notifications on publish: one email per candidate and per interviewer, sent with the existing Google OAuth env vars.
- `EMAIL_DRY_RUN=true` mode: write emails to `data/outbox/` instead of sending. **Default to dry run** so nobody emails real people by accident.

**Frontend**
- Admin run list and run-review screen: interviews, unscheduled candidates, per-interviewer load, publish button. Links to or embeds Person 2's edit panel.
- "My interview" page for candidates and interviewers.

**Provides**
```python
# app/scheduling/runs.py
def save_run(run: ScheduleRun) -> None: ...
def load_run(run_id: str) -> ScheduleRun: ...
def list_runs() -> list[ScheduleRun]: ...
def publish_run(run_id: str) -> ScheduleRun: ...

# app/scheduling/notifications.py
def notify(run: ScheduleRun, users: list[User]) -> NotificationResult: ...
```

**Uses:** `ScheduleRun` from the shared models; `load_inputs` from Person 1 for user names and emails.

**Stable integration functions:** Person 1 and Person 2 may call
`save_run`, `load_run`, `list_runs`, `publish_run`, and `notify` using these
signatures. `list_runs` returns complete runs newest first; `publish_run`
persists the published run and advances the config phase. `notify` returns
counts for sent, dry-run-written, skipped, and failed recipient messages.

**Dummy data:** a hand-written `data/sample_run.json` (a finished `ScheduleRun`), so this work doesn't wait for the solver. Users need `email` fields in the fixtures.

**Owns**
```
app/scheduling/runs.py
app/scheduling/notifications.py
app/routers/runs.py
frontend/src/app/admin/runs/
frontend/src/app/me/
```

## Shared

| File | Owner | Rule |
|---|---|---|
| `app/scheduling/models.py` | all | PR reviewed by all three. Add `Edit` and `Violation` here. |
| `data/testinterviewdata.json` | all | Additive changes only; don't break others' fixtures. |
| `app/main.py` | all | One `include_router` line each. |
| `docs/scheudling-spec.md` | all | Update when a contract changes. |

## Day 0 (together)

1. Move `app/routers/scheduling/models.py` to `app/scheduling/models.py`; delete the stray `backend/routers/` folder.
2. Add `Edit`, `Violation`, and `email` on users to the models and fixtures.
3. Each person commits stubs for their **Provides** functions.
4. Write `data/sample_run.json`.

## Milestones

| When | Goal |
|---|---|
| End of week 1 | Intake data loads into the real solver; review screen renders `sample_run.json`. |
| End of week 2 | Admin runs the solver, edits a draft, publishes, and emails land in `data/outbox/` (dry run). |
| After | Real Gmail send to a test inbox; then Supabase/Postgres and auth replace the stubs. |

## Out of scope for now

- Rescheduling and any edits after a run is published.
- Google Calendar invites.
- Postgres/Supabase persistence and real auth.

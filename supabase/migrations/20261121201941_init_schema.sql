-- =============================================================================
-- RARecruit initial schema. Overview: supabase/README.md.
--   applicants -> applications -> reviews / interviews -> scores -> decisions
-- Only the backend (secret key) touches these tables; RLS is on with no
-- policies. New tables MUST also `enable row level security`.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Enums (add values later with `alter type ... add value`)
-- -----------------------------------------------------------------------------

-- Staff roles. Anyone signed in who is NOT in `interviewers` is a candidate.
create type public.staff_role as enum ('interviewer', 'board', 'admin');

-- Scheduling phase of a cycle; only an admin advances it, in this order.
create type public.cycle_phase as enum ('setup', 'availability', 'booking', 'closed');

-- Which stage a rubric category is used in.
create type public.rubric_stage as enum ('written', 'interview');

-- Where an application is in the funnel. "Decided" isn't a stage: a row in
-- `decisions` is the single source of truth for that.
create type public.application_stage as enum ('written', 'interview', 'withdrawn');

create type public.decision_outcome as enum ('accept', 'reject');


-- =============================================================================
-- Config: cycles, positions, form questions, rubric
-- =============================================================================

create table public.cycles (
  id                                     uuid primary key default gen_random_uuid(),
  name                                   text not null unique,              -- e.g. 'Spring 2027'
  is_active                              boolean not null default false,    -- the cycle the app shows
  phase                                  public.cycle_phase not null default 'setup',

  -- Intake
  google_form_id                         text,                              -- form imported for this cycle
  applications_open_at                   timestamptz,
  applications_close_at                  timestamptz,

  -- Scheduling. Times are stored in UTC; `timezone` (IANA name, validated by
  -- the backend) is used to build the slot grid and to display times.
  timezone                               text not null default 'America/Chicago',
  interview_dates                        date[] not null default '{}',
  daily_start_time                       time,                              -- local, in `timezone`
  daily_end_time                         time,                              -- local, in `timezone`
  slot_length_min                        integer not null default 30,
  panel_size                             integer not null default 2,        -- interviewers per interview
  min_interviewer_minutes                integer not null default 0,        -- min availability per interviewer

  -- Grading. Every rubric category is scored 0..rubric_max_score and counts
  -- equally (no weights).
  rubric_max_score                       integer not null default 5,

  constraint cycles_slot_length_positive   check (slot_length_min > 0),
  constraint cycles_panel_size_positive    check (panel_size >= 1),
  constraint cycles_min_minutes_nonneg     check (min_interviewer_minutes >= 0),
  constraint cycles_rubric_max_positive    check (rubric_max_score > 0),
  constraint cycles_daily_window_order     check (daily_end_time > daily_start_time),
  constraint cycles_application_window     check (applications_close_at > applications_open_at)
);

-- At most one active cycle at a time.
create unique index cycles_one_active on public.cycles (is_active) where is_active;

comment on table public.cycles is
  'One recruiting cycle and all of its config: dates, slot length, panel size, rubric scale, phase.';


-- Positions people can apply for in a cycle: Developer, PM, TL.
-- PMs and TLs have NO written app: their applications skip written review and
-- start at stage 'interview' (has_written_app = false).
create table public.positions (
  id               uuid primary key default gen_random_uuid(),
  cycle_id         uuid not null references public.cycles (id) on delete cascade,
  name             text not null,
  has_written_app  boolean not null default true,   -- false for PM / TL
  sort_order       integer not null default 0,
  unique (cycle_id, name)
);

comment on table public.positions is 'Positions in a cycle (Developer, PM, TL). PM/TL have no written app.';


-- Questions on the cycle's Google Form. `applications.answers` is keyed by
-- `google_question_id`. Name/email questions are NOT listed here: those go to
-- `applicants.full_name` / `applicants.email`.
create table public.form_questions (
  id                  uuid primary key default gen_random_uuid(),
  cycle_id            uuid not null references public.cycles (id) on delete cascade,
  google_question_id  text not null,
  title               text not null,
  sort_order          integer not null default 0,
  show_in_review      boolean not null default true,   -- shown in the written-app review UI
  unique (cycle_id, google_question_id)
);

comment on table public.form_questions is
  'Google Form questions for a cycle, in display order. Keys for applications.answers.';


-- Rubric categories, for written review and for interviews. Shared by all
-- positions; all categories count equally on the cycle's 0..rubric_max_score scale.
create table public.rubric_categories (
  id           uuid primary key default gen_random_uuid(),
  cycle_id     uuid not null references public.cycles (id) on delete cascade,
  stage        public.rubric_stage not null,
  question_id  uuid references public.form_questions (id) on delete set null, -- written: shown beside this question
  name         text not null,
  description  text not null default '',
  sort_order   integer not null default 0,

  constraint rubric_question_only_written check (stage = 'written' or question_id is null)
);

create index rubric_categories_cycle_idx on public.rubric_categories (cycle_id, stage);

comment on table public.rubric_categories is
  'Rubric for a cycle. Written categories can be tied to a form question for side-by-side review.';


-- =============================================================================
-- People
-- =============================================================================

-- On first sign-in the backend matches the email (or `claim_token`), sets
-- `user_id`, and clears the token. After that: `where user_id = <JWT sub>`.

-- Staff. A signed-in user whose id is not in `interviewers.user_id` is a candidate.
create table public.interviewers (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid unique references auth.users (id) on delete set null,  -- null until claimed
  claim_token  uuid unique default gen_random_uuid(),                       -- null once claimed
  email        text not null unique,
  full_name    text not null,
  role         public.staff_role not null default 'interviewer',
  is_active    boolean not null default true,     -- deactivate instead of deleting (keeps history)

  constraint interviewers_email_lowercase check (email = lower(email))
);

comment on table public.interviewers is
  'Interviewers, board and admins. Role lookup is by user_id, linked on first sign-in (email or claim_token).';


-- Applicants. Created by the Google Forms import. The only table with applicant
-- name + email; everything else references applicants by UUID.
create table public.applicants (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid unique references auth.users (id) on delete set null,  -- null until claimed
  claim_token   uuid unique default gen_random_uuid(),                       -- null once claimed
  email         text not null unique,
  full_name     text not null,
  consented_at  timestamptz,                  -- consent to storing name + email

  constraint applicants_email_lowercase check (email = lower(email))
);

comment on table public.applicants is
  'One row per person who applies (name, email). Linked to their sign-in on first sign-in (email or claim_token).';


-- =============================================================================
-- Intake + written review
-- =============================================================================

-- One application per applicant per cycle (created by the Google Forms import).
create table public.applications (
  id                  uuid primary key default gen_random_uuid(),
  -- restrict: a cycle with real applications can't be deleted by accident.
  cycle_id            uuid not null references public.cycles (id) on delete restrict,
  -- cascade: deleting an applicant (e.g. a data-removal request) removes all their data.
  applicant_id        uuid not null references public.applicants (id) on delete cascade,
  position_id         uuid not null references public.positions (id) on delete restrict,
  stage               public.application_stage not null default 'written',
  google_response_id  text unique,                       -- dedupes re-imports
  submitted_at        timestamptz not null default now(),
  answers             jsonb not null default '{}',       -- { google_question_id: answer }

  unique (cycle_id, applicant_id),
  constraint applications_answers_object check (jsonb_typeof(answers) = 'object')
);

create index applications_applicant_idx on public.applications (applicant_id);
create index applications_position_idx  on public.applications (position_id);

comment on table public.applications is
  'An applicant''s form response for one cycle. stage = interview means they may book a slot; decided = has a decisions row. PM/TL start at interview.';


-- A reviewer assigned to an application (Developer apps only; PM/TL have no
-- written app). The row IS the assignment. `comment` is the reviewer's overall
-- summary of the application.
create table public.reviews (
  id              uuid primary key default gen_random_uuid(),
  application_id  uuid not null references public.applications (id) on delete cascade,
  reviewer_id     uuid not null references public.interviewers (id) on delete restrict,
  comment         text not null default '',
  submitted_at    timestamptz,               -- null = not submitted yet

  unique (application_id, reviewer_id)
);

create index reviews_reviewer_idx on public.reviews (reviewer_id);

comment on table public.reviews is 'Written-app review assignment + overall comment for one reviewer.';


-- One score per (review, rubric category). The written feedback is the
-- review's overall `comment`.
create table public.review_scores (
  review_id           uuid not null references public.reviews (id) on delete cascade,
  rubric_category_id  uuid not null references public.rubric_categories (id) on delete restrict,
  score               numeric(5, 2) not null,

  primary key (review_id, rubric_category_id),
  constraint review_scores_nonneg check (score >= 0)
);

create index review_scores_category_idx on public.review_scores (rubric_category_id);

comment on table public.review_scores is 'Structured written-app scores, per rubric category.';


-- =============================================================================
-- Scheduling (self-reserve)
-- =============================================================================

-- An interviewer's availability range. Ranges need not align to the slot grid;
-- an interviewer is free for a slot if the slot lies fully inside one range.
-- Overlapping ranges are harmless (the backend merges them when computing).
create table public.availability (
  id              uuid primary key default gen_random_uuid(),
  cycle_id        uuid not null references public.cycles (id) on delete cascade,
  interviewer_id  uuid not null references public.interviewers (id) on delete cascade,
  start_at        timestamptz not null,
  end_at          timestamptz not null,

  constraint availability_range_order check (end_at > start_at)
);

create index availability_cycle_idx on public.availability (cycle_id, start_at);

comment on table public.availability is 'Interviewer availability ranges (UTC).';


-- Conflicts of interest: this interviewer must never be on this applicant's panel.
create table public.recusals (
  interviewer_id  uuid not null references public.interviewers (id) on delete cascade,
  applicant_id    uuid not null references public.applicants (id) on delete cascade,

  primary key (interviewer_id, applicant_id)
);

create index recusals_applicant_idx on public.recusals (applicant_id);

comment on table public.recusals is 'Conflicts of interest between an interviewer and an applicant.';


-- Slot grid, generated by the backend. A time, not a seat: several candidates
-- can book the same slot with different panels.
create table public.slots (
  id          uuid primary key default gen_random_uuid(),
  cycle_id    uuid not null references public.cycles (id) on delete cascade,
  start_at    timestamptz not null,
  end_at      timestamptz not null,

  unique (cycle_id, start_at),
  constraint slots_range_order check (end_at > start_at)
);

comment on table public.slots is 'Fixed-length interview slots for a cycle (UTC), generated by the backend.';


-- A booked interview. Cancelled rows are kept for history (cancelled_at set);
-- an interview is active while cancelled_at is null.
create table public.interviews (
  id              uuid primary key default gen_random_uuid(),
  application_id  uuid not null references public.applications (id) on delete cascade,
  slot_id         uuid not null references public.slots (id) on delete restrict,
  gcal_event_id   text unique,          -- Google Calendar event, set after the invite is sent
  booked_at       timestamptz not null default now(),
  cancelled_at    timestamptz,          -- null = active

  -- Target for interview_panelists' composite FK (keeps panelists.slot_id in sync).
  unique (id, slot_id)
);

-- A candidate holds at most one active interview per application.
create unique index interviews_one_active_per_application
  on public.interviews (application_id)
  where cancelled_at is null;

create index interviews_slot_idx on public.interviews (slot_id);

comment on table public.interviews is 'Booked interviews. Write via book_interview() / cancel_interview().';


-- Panel for an interview + each panelist's overall `comment`. `slot_id` is
-- copied from the interview so unique (interviewer_id, slot_id) blocks
-- double-booking. Rows are removed on cancel, freeing the interviewer.
create table public.interview_panelists (
  interview_id    uuid not null,
  interviewer_id  uuid not null references public.interviewers (id) on delete restrict,
  slot_id         uuid not null,
  comment         text not null default '',   -- panelist's overall summary of the interview

  primary key (interview_id, interviewer_id),
  unique (interviewer_id, slot_id),     -- no double-booking
  foreign key (interview_id, slot_id)
    references public.interviews (id, slot_id) on update cascade on delete cascade
);

comment on table public.interview_panelists is 'Interviewers on each interview. Unique per (interviewer, slot).';


-- One score per (interview, panelist, rubric category). The composite FK means
-- only panelists can score, and a scored panelist can't be swapped out.
create table public.interview_scores (
  interview_id        uuid not null references public.interviews (id) on delete cascade,
  interviewer_id      uuid not null,
  rubric_category_id  uuid not null references public.rubric_categories (id) on delete restrict,
  score               numeric(5, 2) not null,

  primary key (interview_id, interviewer_id, rubric_category_id),
  -- NO ACTION (checked at end of statement): deleting a whole interview cascades
  -- through both FKs fine, but deleting just a scored panelist fails.
  foreign key (interview_id, interviewer_id)
    references public.interview_panelists (interview_id, interviewer_id),
  constraint interview_scores_nonneg check (score >= 0)
);

create index interview_scores_category_idx on public.interview_scores (rubric_category_id);

comment on table public.interview_scores is 'Structured interview scores, per panelist and rubric category.';


-- =============================================================================
-- Decisions
-- =============================================================================

create table public.decisions (
  application_id  uuid primary key references public.applications (id) on delete cascade,
  outcome         public.decision_outcome not null,
  decided_by      uuid references public.interviewers (id) on delete restrict,
  notes           text not null default '',
  decided_at      timestamptz not null default now()
);

comment on table public.decisions is 'Final accept / reject per application.';


-- =============================================================================
-- Booking RPCs: supabase-py can't run transactions, so these write an interview
-- and its whole panel all-or-nothing. The backend picks the panel; on a race,
-- unique (interviewer_id, slot_id) raises 23505 and the backend retries.
-- =============================================================================

-- Book a new interview, or move an existing active one (reschedule).
--
-- Params:
--   p_application_id  application the interview is for
--   p_slot_id         slot to book
--   p_interviewer_ids the panel; must be exactly cycles.panel_size distinct ids
--   p_interview_id    null = new booking; otherwise the active interview to move
-- Returns: the interview id.
-- Errors:  P0002 not found, 22023 bad panel / wrong cycle, 23505 interviewer
--          already booked in that slot or application already has an interview.
create function public.book_interview(
  p_application_id  uuid,
  p_slot_id         uuid,
  p_interviewer_ids uuid[],
  p_interview_id    uuid default null
)
returns uuid
language plpgsql
set search_path = ''
as $$
declare
  v_panel_size    integer;
  v_slot_cycle    uuid;
  v_app_cycle     uuid;
  v_interview_id  uuid;
begin
  -- Look up the slot's cycle and that cycle's panel size.
  select s.cycle_id, c.panel_size
    into v_slot_cycle, v_panel_size
    from public.slots s
    join public.cycles c on c.id = s.cycle_id
   where s.id = p_slot_id;
  if v_slot_cycle is null then
    raise exception 'slot % not found', p_slot_id using errcode = 'P0002';
  end if;

  -- The slot must belong to the application's cycle.
  select a.cycle_id into v_app_cycle
    from public.applications a
   where a.id = p_application_id;
  if v_app_cycle is null then
    raise exception 'application % not found', p_application_id using errcode = 'P0002';
  end if;
  if v_app_cycle <> v_slot_cycle then
    raise exception 'slot % is not in the application''s cycle', p_slot_id using errcode = '22023';
  end if;

  -- Panel must be exactly panel_size distinct interviewers.
  if coalesce(cardinality(p_interviewer_ids), 0) <> v_panel_size
     or (select count(distinct x) from unnest(p_interviewer_ids) as x) <> v_panel_size then
    raise exception 'panel must have exactly % distinct interviewers', v_panel_size using errcode = '22023';
  end if;

  if p_interview_id is null then
    -- New booking.
    insert into public.interviews (application_id, slot_id)
    values (p_application_id, p_slot_id)
    returning id into v_interview_id;
  else
    -- Reschedule: drop the old panel, then move the interview. (Fails if any
    -- panelist already has scores, via interview_scores' FK.)
    delete from public.interview_panelists where interview_id = p_interview_id;

    update public.interviews
       set slot_id = p_slot_id
     where id = p_interview_id
       and application_id = p_application_id
       and cancelled_at is null
    returning id into v_interview_id;

    if v_interview_id is null then
      raise exception 'active interview % not found for this application', p_interview_id
        using errcode = 'P0002';
    end if;
  end if;

  -- Write the panel in one statement.
  insert into public.interview_panelists (interview_id, interviewer_id, slot_id)
  select v_interview_id, x, p_slot_id
    from unnest(p_interviewer_ids) as x;

  return v_interview_id;
end;
$$;

comment on function public.book_interview(uuid, uuid, uuid[], uuid) is
  'Atomically book or reschedule an interview with its panel. Backend-only (service role).';


-- Cancel an active interview and free its panel's slot.
--
-- Params:  p_interview_id  the interview to cancel
-- Errors:  P0002 if it doesn't exist or is already cancelled.
create function public.cancel_interview(p_interview_id uuid)
returns void
language plpgsql
set search_path = ''
as $$
begin
  update public.interviews
     set cancelled_at = now()
   where id = p_interview_id
     and cancelled_at is null;

  if not found then
    raise exception 'active interview % not found', p_interview_id using errcode = 'P0002';
  end if;

  -- Free the interviewers for that slot.
  delete from public.interview_panelists where interview_id = p_interview_id;
end;
$$;

comment on function public.cancel_interview(uuid) is
  'Cancel an active interview and release its panelists. Backend-only (service role).';


-- =============================================================================
-- RLS on with no policies, plus revoked default grants: anon/authenticated get
-- nothing. service_role (the backend) bypasses RLS.
-- =============================================================================

alter table public.cycles              enable row level security;
alter table public.positions           enable row level security;
alter table public.form_questions      enable row level security;
alter table public.rubric_categories   enable row level security;
alter table public.interviewers        enable row level security;
alter table public.applicants          enable row level security;
alter table public.applications        enable row level security;
alter table public.reviews             enable row level security;
alter table public.review_scores       enable row level security;
alter table public.availability        enable row level security;
alter table public.recusals            enable row level security;
alter table public.slots               enable row level security;
alter table public.interviews          enable row level security;
alter table public.interview_panelists enable row level security;
alter table public.interview_scores    enable row level security;
alter table public.decisions           enable row level security;

-- Tables: backend only.
revoke all on all tables in schema public from anon, authenticated;
grant select, insert, update, delete on all tables in schema public to service_role;

-- Functions: functions are executable by PUBLIC by default; lock them down.
revoke execute on all functions in schema public from public, anon, authenticated;
grant execute on function public.book_interview(uuid, uuid, uuid[], uuid) to service_role;
grant execute on function public.cancel_interview(uuid) to service_role;

-- Future objects created by migrations (run as `postgres`) start locked too.
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;

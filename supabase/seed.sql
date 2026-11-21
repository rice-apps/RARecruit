-- =============================================================================
-- DEV-ONLY fake data. NEVER run against prod. Run in SQL Editor after the
-- migrations. All people are fake (@example.com).
--
-- IDs are fixed so rows are easy to reference. Prefix by table:
--   c1 cycle, 0a positions, 0b questions, 0c rubric, 0d interviewers,
--   0e applicants, 0f applications
-- Every insert is `on conflict do nothing`, so re-running is harmless.
-- =============================================================================

-- Cycle: interviews on Dec 7-8 2026, 10:00-21:00 Chicago time, 30 min, panel of 2.
insert into public.cycles (
  id, name, is_active, phase, applications_open_at, applications_close_at,
  timezone, interview_dates, daily_start_time, daily_end_time,
  slot_length_min, panel_size, rubric_max_score
) values (
  'c1000000-0000-4000-8000-000000000001', 'Spring 2027 (dev seed)', true, 'booking',
  '2026-11-01 00:00-06', '2026-11-15 23:59-06',
  'America/Chicago', '{2026-12-07,2026-12-08}', '10:00', '21:00',
  30, 2, 5
) on conflict do nothing;

-- PM and TL have no written app.
insert into public.positions (id, cycle_id, name, has_written_app, sort_order) values
  ('0a000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'Developer',       true,  1),
  ('0a000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 'Product Manager', false, 2),
  ('0a000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000001', 'Team Lead',       false, 3)
on conflict do nothing;

insert into public.form_questions (id, cycle_id, google_question_id, title, sort_order) values
  ('0b000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'q_why',     'Why do you want to join RiceApps?', 1),
  ('0b000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 'q_project', 'Tell us about a project you are proud of.', 2),
  ('0b000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000001', 'q_team',    'Describe a time you worked through a disagreement on a team.', 3)
on conflict do nothing;

insert into public.rubric_categories (id, cycle_id, stage, question_id, name, description, sort_order) values
  ('0c000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'written',   '0b000000-0000-4000-8000-000000000001', 'Motivation',      'Clear, specific reasons for joining.', 1),
  ('0c000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 'written',   '0b000000-0000-4000-8000-000000000002', 'Technical depth', 'Owns real technical decisions.',       2),
  ('0c000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000001', 'written',   '0b000000-0000-4000-8000-000000000003', 'Collaboration',   'Resolves conflict constructively.',    3),
  ('0c000000-0000-4000-8000-000000000004', 'c1000000-0000-4000-8000-000000000001', 'interview', null,                                   'Communication',   'Explains ideas clearly.',              1),
  ('0c000000-0000-4000-8000-000000000005', 'c1000000-0000-4000-8000-000000000001', 'interview', null,                                   'Problem solving', 'Breaks down an unfamiliar problem.',   2)
on conflict do nothing;

-- Staff: 1 admin, 1 board, 3 interviewers.
insert into public.interviewers (id, email, full_name, role) values
  ('0d000000-0000-4000-8000-000000000001', 'ana@example.com', 'Ana Admin', 'admin'),
  ('0d000000-0000-4000-8000-000000000002', 'ben@example.com', 'Ben Board', 'board'),
  ('0d000000-0000-4000-8000-000000000003', 'chi@example.com', 'Chi Park',  'interviewer'),
  ('0d000000-0000-4000-8000-000000000004', 'dee@example.com', 'Dee Ortiz', 'interviewer'),
  ('0d000000-0000-4000-8000-000000000005', 'eli@example.com', 'Eli Brown', 'interviewer')
on conflict do nothing;

insert into public.applicants (id, email, full_name, consented_at) values
  ('0e000000-0000-4000-8000-000000000001', 'alex@example.com', 'Alex Kim',    now()),
  ('0e000000-0000-4000-8000-000000000002', 'blair@example.com', 'Blair Singh', now()),
  ('0e000000-0000-4000-8000-000000000003', 'casey@example.com', 'Casey Lee',   now()),
  ('0e000000-0000-4000-8000-000000000004', 'drew@example.com', 'Drew Patel',  now()),
  ('0e000000-0000-4000-8000-000000000005', 'emery@example.com', 'Emery Wu',    now()),
  ('0e000000-0000-4000-8000-000000000006', 'finn@example.com', 'Finn Novak',  now())
on conflict do nothing;

-- Applications: devs 1+3 passed written review, 5 is in review, 6 was rejected at the
-- written stage. PM (2) and TL (4) have no written app, so they start at 'interview'.
insert into public.applications (id, cycle_id, applicant_id, position_id, stage, google_response_id, submitted_at, answers) values
  ('0f000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', '0e000000-0000-4000-8000-000000000001', '0a000000-0000-4000-8000-000000000001', 'interview', 'seed-resp-1', '2026-11-03 12:00-06',
   '{"q_why": "I want to build apps for nonprofits.", "q_project": "Built a dorm laundry tracker in React.", "q_team": "Mediated a design disagreement by prototyping both options."}'),
  ('0f000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', '0e000000-0000-4000-8000-000000000002', '0a000000-0000-4000-8000-000000000002', 'interview', 'seed-resp-2', '2026-11-04 12:00-06', '{}'),
  ('0f000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000001', '0e000000-0000-4000-8000-000000000003', '0a000000-0000-4000-8000-000000000001', 'interview', 'seed-resp-3', '2026-11-05 12:00-06',
   '{"q_why": "To learn from experienced devs.", "q_project": "Wrote a Python CLI for course planning.", "q_team": "Split work by strengths after a conflict over scope."}'),
  ('0f000000-0000-4000-8000-000000000004', 'c1000000-0000-4000-8000-000000000001', '0e000000-0000-4000-8000-000000000004', '0a000000-0000-4000-8000-000000000003', 'interview', 'seed-resp-4', '2026-11-06 12:00-06', '{}'),
  ('0f000000-0000-4000-8000-000000000005', 'c1000000-0000-4000-8000-000000000001', '0e000000-0000-4000-8000-000000000005', '0a000000-0000-4000-8000-000000000001', 'written',   'seed-resp-5', '2026-11-07 12:00-06',
   '{"q_why": "Friends recommended it.", "q_project": "Made a personal website.", "q_team": "Talked it out."}'),
  ('0f000000-0000-4000-8000-000000000006', 'c1000000-0000-4000-8000-000000000001', '0e000000-0000-4000-8000-000000000006', '0a000000-0000-4000-8000-000000000001', 'written',   'seed-resp-6', '2026-11-08 12:00-06',
   '{"q_why": "Resume.", "q_project": "N/A", "q_team": "N/A"}')
on conflict do nothing;

-- Reviewer assignments (Developer apps only). Application 1 has a submitted review with scores.
insert into public.reviews (application_id, reviewer_id, comment, submitted_at) values
  ('0f000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000003', 'Strong, specific answers.', '2026-11-16 18:00-06'),
  ('0f000000-0000-4000-8000-000000000005', '0d000000-0000-4000-8000-000000000005', '', null),
  ('0f000000-0000-4000-8000-000000000006', '0d000000-0000-4000-8000-000000000004', 'Answers were too thin.', '2026-11-16 19:00-06')
on conflict do nothing;

insert into public.review_scores (review_id, rubric_category_id, score)
select r.id, v.category_id::uuid, v.score
  from public.reviews r
 cross join (values
   ('0c000000-0000-4000-8000-000000000001', 4.0),
   ('0c000000-0000-4000-8000-000000000002', 5.0),
   ('0c000000-0000-4000-8000-000000000003', 3.5)
 ) as v (category_id, score)
 where r.application_id = '0f000000-0000-4000-8000-000000000001'
on conflict do nothing;

insert into public.decisions (application_id, outcome, decided_by, notes) values
  ('0f000000-0000-4000-8000-000000000006', 'reject', '0d000000-0000-4000-8000-000000000002', 'Did not advance past written round.')
on conflict do nothing;

-- Interviewer availability (CST = UTC-6 in December).
insert into public.availability (cycle_id, interviewer_id, start_at, end_at) values
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000002', '2026-12-07 12:00-06', '2026-12-07 14:00-06'),
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000003', '2026-12-07 17:00-06', '2026-12-07 20:00-06'),
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000004', '2026-12-07 17:00-06', '2026-12-07 19:00-06'),
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000005', '2026-12-07 18:00-06', '2026-12-07 21:00-06'),
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000001', '2026-12-08 12:00-06', '2026-12-08 14:00-06'),
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000003', '2026-12-08 12:00-06', '2026-12-08 15:00-06'),
  ('c1000000-0000-4000-8000-000000000001', '0d000000-0000-4000-8000-000000000004', '2026-12-08 13:00-06', '2026-12-08 16:00-06')
on conflict do nothing;

-- Dee has a conflict of interest with Casey.
insert into public.recusals (interviewer_id, applicant_id) values
  ('0d000000-0000-4000-8000-000000000004', '0e000000-0000-4000-8000-000000000003')
on conflict do nothing;

-- Slot grid for every interview date: daily_start..daily_end in slot_length steps,
-- built in local time then converted to UTC. (In real use the backend does this.)
insert into public.slots (cycle_id, start_at, end_at)
select c.id,
       local_start at time zone c.timezone,
       (local_start + make_interval(mins => c.slot_length_min)) at time zone c.timezone
  from public.cycles c
 cross join lateral unnest(c.interview_dates) as d (day)
 cross join lateral generate_series(
       d.day + c.daily_start_time,
       d.day + c.daily_end_time - make_interval(mins => c.slot_length_min),
       make_interval(mins => c.slot_length_min)
     ) as local_start
 where c.id = 'c1000000-0000-4000-8000-000000000001'
on conflict do nothing;

-- Alex booked Dec 7 6:00 PM with Chi + Dee (skipped if already booked).
select public.book_interview(
  '0f000000-0000-4000-8000-000000000001',
  (select id from public.slots
    where cycle_id = 'c1000000-0000-4000-8000-000000000001'
      and start_at = '2026-12-07 18:00-06'),
  array['0d000000-0000-4000-8000-000000000003', '0d000000-0000-4000-8000-000000000004']::uuid[]
)
where not exists (
  select 1 from public.interviews
   where application_id = '0f000000-0000-4000-8000-000000000001'
     and cancelled_at is null
);

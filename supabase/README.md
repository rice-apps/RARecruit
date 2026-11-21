# Supabase

Your `.env` points at the **dev** project, which has fake data. TLs own the schema (`migrations/`) and project settings; ask a TL to change the schema or to add you as staff.

## Accessing data

- Only the backend reads and writes tables, with `from app.db import supabase` (secret key). The frontend uses Supabase **only for sign-in**.
- The secret key bypasses RLS, so **check the user's role in the route** before touching data.
- Look people up by `user_id = <JWT sub>`. Emails live only in `interviewers` and `applicants`; everything else references people by UUID.

## Tables

| Table | Notes |
|---|---|
| `cycles` | Config for one cycle: dates, timezone, slot length, `panel_size`, `rubric_max_score`, `phase` (`setup → availability → booking → closed`). One has `is_active = true`. The slot grid is computed from this; it isn't stored. `form_questions` = the Google Form's questions in order (`[{google_question_id, title, show_in_review}]`), keys for `applications.answers`. |
| `rubric_categories` | `written` categories are scored per category, `0..rubric_max_score`, all equal, and can point at a question (`google_question_id`). `interview` categories are guidance only. |
| `interviewers` | Staff: `interviewer` / `board` / `admin`. Not listed = candidate. |
| `applicants` | Name, email, consent. |
| `applications` | One per applicant per cycle. `position` = `developer / pm / tl` (only developers have a written app, so PM/TL start at `interview`). `stage` = `written / interview / withdrawn`. Decision: `decision` (`accept / reject`, null = undecided), `decided_by`, `decided_at`, `decision_notes`. |
| `reviews` | Reviewer assignment, overall `comment`, `submitted_at` (null = not submitted). |
| `review_scores` | Score per (review, category). |
| `availability` | Interviewer time ranges (UTC). |
| `recusals` | (interviewer, applicant) conflict of interest. |
| `interviews` | `start_at` / `end_at`, plus the panel's **one** combined `score` and `comment`. One active interview per application; `cancelled_at` null = active. Several interviews can share a start time. |
| `interview_panelists` | Panel. An interviewer can't be in two interviews at the same start time. |

## Booking interviews

Don't insert into `interviews` or `interview_panelists` directly. Use these two database functions, which save the interview and its whole panel all-or-nothing:

```python
supabase.rpc("book_interview", {
    "p_application_id": app_id,
    "p_start_at": start_at,          # a grid time from the cycle config
    "p_interviewer_ids": [i1, i2],   # exactly cycles.panel_size
    "p_interview_id": None,          # an existing id = reschedule
}).execute()

supabase.rpc("cancel_interview", {"p_interview_id": interview_id}).execute()
```

If `book_interview` fails with error `23505`, an interviewer was just taken by another booking, or the application already has an interview. Pick another panel and retry. Once an interview has a `score`, it can't be rescheduled or cancelled.

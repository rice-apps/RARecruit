# Supabase

Your `.env` points at the **dev** project, which has fake data. TLs own the schema (`migrations/`) and project settings; ask a TL to change the schema or to add you as staff.

## Accessing data

- Only the backend reads and writes tables, with `from app.db import supabase` (secret key). The frontend uses Supabase **only for sign-in**.
- The secret key bypasses RLS, so **check the user's role in the route** before touching data.
- Look people up by `user_id = <JWT sub>`. Emails live only in `interviewers` and `applicants`; everything else references people by UUID.

## Tables

| Table | Notes |
|---|---|
| `cycles` | Config for one cycle: dates, timezone, slot length, `panel_size`, `rubric_max_score`, `phase` (`setup → availability → booking → closed`). One has `is_active = true`. |
| `positions` | Developer, PM, TL. PM/TL have `has_written_app = false` and start at stage `interview`. |
| `form_questions` | Google Form questions; keys for `applications.answers`. |
| `rubric_categories` | `written` or `interview`. All categories are equal and scored `0..rubric_max_score`. |
| `interviewers` | Staff: `interviewer` / `board` / `admin`. Not listed = candidate. |
| `applicants` | Name, email, consent. |
| `applications` | One per applicant per cycle. `stage` = `written / interview / withdrawn`; decided = has a `decisions` row. |
| `reviews` | Reviewer assignment, overall `comment`, `submitted_at` (null = not submitted). |
| `review_scores` | Score per (review, category). |
| `availability` | Interviewer time ranges (UTC). |
| `recusals` | (interviewer, applicant) conflict of interest. |
| `slots` | Slot grid. A time, not a seat: several interviews can share a slot. |
| `interviews` | One active interview per application. `cancelled_at` null = active. |
| `interview_panelists` | Panel plus each panelist's overall `comment`. An interviewer can't be in two interviews in the same slot. |
| `interview_scores` | Score per (interview, panelist, category). Only panelists can score. |
| `decisions` | Accept / reject. |

## Booking interviews

Don't insert into `interviews` or `interview_panelists` directly. Use these two database functions, which save the interview and its whole panel all-or-nothing:

```python
supabase.rpc("book_interview", {
    "p_application_id": app_id,
    "p_slot_id": slot_id,
    "p_interviewer_ids": [i1, i2],   # exactly cycles.panel_size
    "p_interview_id": None,          # an existing id = reschedule
}).execute()

supabase.rpc("cancel_interview", {"p_interview_id": interview_id}).execute()
```

If `book_interview` fails with error `23505`, an interviewer was just taken by another booking, or the application already has an interview. Pick another panel and retry.

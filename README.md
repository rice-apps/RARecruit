# RARecruit
Official RARecruit repo: RiceApps' internal recruiting platform. See [project/architecture.md](project/architecture.md) for the architecture diagram.

## Setup

### Prerequisites

- **Node.js 20.9+** (`node -v`)
- **uv:**

For Mac/Linux:
```bash
brew install uv
```
OR
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For Windows:
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
OR
```bash
winget install --id=astral-sh.uv -e
```

### Install dependencies

```bash
cd frontend && npm install
cd ../backend && uv sync 
```

To add a package:
- **Frontend:** `npm install <package>`, then commit `package.json` and `package-lock.json`.
- **Backend:** `uv add <package>` (or `uv add --dev <package>`), then commit `pyproject.toml` and `uv.lock`.

### Environment variables

Each app has its own `.env.example` for you to copy and fill in the values (ask TLs; use the **dev** Supabase project):
```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```
Whenever you add a variable, add it to the matching `.env.example` too.

## Startup

Run both in separate terminals.

**Frontend** at http://localhost:3000:
```bash
cd frontend
npm run dev
```

**Backend** at http://localhost:8000 (interactive API docs at `/docs`):
```bash
cd backend
uv run uvicorn app.main:app --reload
```

**Lint & test:**
```bash
cd frontend && npm run lint
cd backend && uv run ruff check . && uv run pytest
```

## Repo structure
Some folders do not exist yet:
```text
RARecruit/
├── frontend/                # Next.js (App Router, TS) + Tailwind
│   ├── src/app/             # pages and layouts
│   ├── src/lib/             # Supabase client, API client (planned)
│   └── .env.example
├── backend/                 # FastAPI, managed by uv
│   ├── app/
│   │   ├── main.py          # FastAPI app, includes routers
│   │   └── routers/         # add a file when you add a feature
│   ├── tests/               # (planned)
│   ├── pyproject.toml
│   ├── uv.lock
│   └── .env.example
├── supabase/                # (planned)
│   ├── migrations/          # schema
│   └── seed.sql             # fake data (dev only)
├── project/
│   └── architecture.md      # architecture diagram
├── .gitignore               # Node and Python
└── README.md
```

# Policies & best practices

## Branches

Create a new branch each time you start working on a NEW feature.

**Branch naming scheme:**
`<app>/<type>-<name>`:

| Working on | Branch |
|---|---|
| Frontend feature | `frontend/feat-<feature_name>` |
| Frontend fix | `frontend/fix-<fix_name>` |
| Backend feature | `backend/feat-<feature_name>` |
| Backend fix | `backend/fix-<fix_name>` |
| Anything else | `misc/<name>` |

**Process:**
```
git pull
git switch -c <new branch name>
```
Do NOT push to the main branch. Only focus on your feature branch.
```
git add <your files> (no env!)
git commit -m <message>
git push -u origin <your branch name>
```
Once you have completed working on your feature branch, raise a PR for team leads to review. Add `uma-menon` and `mertyercel` as reviewers.

## PRs

- **PR Title: Add Notion Ticket to the title alongside a short description**
- Features added
- Dependencies added
- High-level changes per file
- Concerns or potential conflicts

## Documentation

- Leave inline comments everywhere
- Documentation for all methods (purpose, parameters, retvals)

## Learn More

To learn more about our tech stack, please make use of the following:
 - [FastAPI Docs](https://fastapi.tiangolo.com/)
 - [Python Docs](https://docs.python.org/3/)
 - [uv Docs](https://docs.astral.sh/uv/)
 - [Supabase Docs](https://supabase.com/docs)
 - [Next.js Docs](https://nextjs.org/docs)
 - [Learn Next.js](https://nextjs.org/learn)
 - [Tailwind Docs](https://tailwindcss.com/docs)


## Updated ENV File

For the application to work, please have the same variables as [.env.example](.env.example) in your .env file.

# CLAUDE.md — Standing Instructions for Claude Code
## DevOps Job Portal Project

This file is read by Claude Code at the start of every session.
Follow every instruction in this file without exception unless explicitly told otherwise by the user.

---

## 1. Git Workflow — Mandatory for Every Task

### 1.1 Before Writing Any Code

Run these commands first. Do not skip this step.

```bash
# Step 1 — Check which branch you are on
git branch

# Step 2 — If you are NOT already on a feature branch, create one
git checkout develop
git pull origin develop
git checkout -b feature/TASK-XXX-short-description
# Replace XXX with the task number from tasks.md
# Replace short-description with 2-4 words describing the task
# Example: feature/TASK-005-remoteok-scraper
```

If already on the correct feature branch, just confirm with `git status` and proceed.

**Never start work on `main` or `develop` directly.**

---

### 1.2 Commit Message Format

Every commit must follow this format:

```
type: short description of what was done

Types:
  feat     → new file, new function, new feature
  fix      → bug fix
  chore    → config, tooling, env files, non-code changes
  docs     → documentation, comments, README updates
  test     → adding or modifying tests
  refactor → restructuring code without changing behaviour

Examples:
  feat: add RemoteOK scraper module
  feat: build location tagger with priority logic
  fix: handle missing posted_date from Jobicy API
  chore: add companies.yaml with initial 108 companies
  test: add unit tests for keyword filter module
  docs: update README with local run instructions
```

---

### 1.3 Committing During Work

Do not make one giant commit at the end. Commit logically as work progresses.

```bash
# After completing a logical unit of work (one function, one file, one feature)
git add <specific-file-or-directory>
git commit -m "feat: description of what this commit does"
```

Example progression for TASK-005 (RemoteOK scraper):

```bash
# After writing the fetch function
git add backend/scraper/sources/remoteok.py
git commit -m "feat: add RemoteOK API fetch with User-Agent header"

# After adding keyword filter integration
git commit -m "feat: integrate keyword filter into RemoteOK module"

# After adding DB write and logging
git commit -m "feat: add DB write and scrape log for RemoteOK"
```

---

### 1.4 After Completing a Task

```bash
# Confirm all changes are tracked
git status

# Stage anything unstaged
git add .

# Final commit
git commit -m "feat: complete TASK-XXX short description"

# Push to GitHub
git push origin feature/TASK-XXX-short-description

# Remind the user:
# "Task complete. Branch pushed to GitHub.
#  Please open a Pull Request on GitHub:
#  Base: develop | Compare: feature/TASK-XXX-short-description
#  After merging, run: git checkout develop && git pull origin develop
#  Then we can start the next task."
```

---

### 1.5 Commands That Are Forbidden

Never run these under any circumstances:

```bash
git push origin main          # FORBIDDEN — main is protected
git push --force              # FORBIDDEN — no force pushes ever
git commit -m "update"        # FORBIDDEN — vague commit messages
git commit -m "fix"           # FORBIDDEN — must describe what was fixed
git checkout main             # AVOID — only Claude Code should be on feature branches
```

---

## 2. Project Structure

```
devops-job-portal/
├── backend/
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── main.py                  # Scraper orchestrator — cron entry point
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── remoteok.py          # Source A1
│   │   │   ├── remotive.py          # Source A2
│   │   │   ├── jobicy.py            # Source A3
│   │   │   ├── arbeitnow.py         # Source A4
│   │   │   ├── hn_algolia.py        # Source A5
│   │   │   └── ats/
│   │   │       ├── __init__.py
│   │   │       ├── greenhouse.py    # Source B1
│   │   │       ├── lever.py         # Source B2
│   │   │       └── ashby.py         # Source B3
│   │   ├── filters.py               # Keyword filter and role type detection
│   │   ├── tagger.py                # Location priority tagger
│   │   └── logger.py                # Scrape run logger
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application
│   │   └── models.py                # Pydantic response models
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py              # SQLite connection and query helpers
│   │   └── schema.sql               # Table definitions
│   ├── config/
│   │   ├── companies.yaml           # Source B company list — edit to add companies
│   │   └── settings.py              # Environment variable loader
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_filters.py
│   │   └── test_tagger.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── Dockerfile
├── docs/
│   ├── requirements.md
│   ├── prd.md
│   └── tasks.md
├── docker-compose.yml
├── CLAUDE.md                        # This file — do not modify without user instruction
├── .env.example
├── .gitignore
└── README.md
```

---

## 3. Key Architectural Rules

### 3.1 Scraper and Frontend Are Fully Decoupled

The scraper and the web page must never be connected.

```
CORRECT:
  Cron (6AM IST) → scraper runs → writes to SQLite → done
  User visits page → FastAPI reads SQLite → returns cached JSON → page renders

WRONG — never do this:
  User visits page → page triggers scraper → scraper hits external APIs
  Page refresh → new scrape triggered
```

**The page must never cause a live API call to any external job source.**
The only outbound HTTP calls happen inside `scraper/main.py` during the scheduled run.

---

### 3.2 Scraper Runs Once Per Day

The scraper is triggered by cron at 06:00 IST (00:30 UTC). It runs once. It does not run again until the next day. There are no on-demand scrape endpoints in the API.

---

### 3.3 All Filtering is Client-Side

The FastAPI backend returns all jobs in one response. The frontend JavaScript filters that data in memory. There are no filter query parameters on `/api/jobs`. No server round-trip happens when the user changes a filter.

---

### 3.4 The API Has No Write Endpoints

FastAPI exposes only:
- `GET /api/jobs` — read jobs from DB
- `GET /api/health` — read scrape status from DB

No POST, PUT, DELETE, or PATCH endpoints. No scraper trigger endpoint.

---

## 4. Compliance Rules — Non-Negotiable

These rules apply to every scraper module. They must be implemented without exception.

### 4.1 User-Agent Header

Every outbound HTTP request must include this exact header:

```python
headers = {
    "User-Agent": "DevOpsJobsPortal/1.0 (personal project; contact: your@email.com)",
    "Accept": "application/json"
}
```

Never make an HTTP request without this header.

---

### 4.2 Fetch Frequency Per Source

| Source | Maximum Calls Per Day | Notes |
|---|---|---|
| RemoteOK | 1 | Once — no retries unless error |
| Remotive | 4 | 1 per keyword search — stay under 4 total |
| Jobicy | 1 per hour max | Daily cron = 1 call per keyword — safe |
| Arbeitnow | 1 | Be respectful |
| HN Algolia | 1 | Thread search + comment fetch |
| Greenhouse | 1 per company slug | With 1s sleep between companies |
| Lever | 1 per company slug | With 1s sleep between companies |
| Ashby | 1 per company slug | With 1s sleep between companies |

Always add `time.sleep(1)` between individual company ATS calls.

---

### 4.3 Attribution Fields — Required in DB

Every job record written to the database must have:
- `source_name` — human-readable source platform name
- `source_url` — clickable link back to the source platform
- `apply_url` — original job posting URL on the source platform

These fields must never be empty or null.

---

### 4.4 Error Handling Per Source

Every source must be wrapped in try/except:

```python
try:
    jobs = fetch_from_source()
    write_to_db(jobs)
    log_success(source_name, len(jobs))
except Exception as e:
    log_failure(source_name, str(e))
    # Do NOT raise — continue to next source
```

A single source failure must never stop the rest of the scraper from running.

---

### 4.5 No Email Gating

Jobs must never be placed behind any form of email capture, signup, or login. The portal is fully public and open.

---

### 4.6 Working Nomads is Excluded

Do not add Working Nomads as a source. Their free public API is not confirmed. Do not implement it.

---

## 5. Code Standards

### 5.1 Python

- Python 3.11+
- Use `requests` for HTTP calls (not httpx, not aiohttp — keep it simple)
- Use `pydantic` for data validation in the API layer
- Use `sqlite3` (stdlib) for database in Phase 1 — no ORM
- Use `python-dotenv` to load `.env` files
- Use `pytest` for tests
- Follow PEP 8 — 4-space indentation, snake_case variables, UPPER_CASE constants
- Add docstrings to all functions

```python
def fetch_jobs(slug: str) -> list[dict]:
    """
    Fetch jobs from Greenhouse ATS for a given company slug.

    Args:
        slug: Company identifier on Greenhouse (e.g. 'cloudflare')

    Returns:
        List of normalised job dicts ready for DB insertion.
        Returns empty list on error (logged separately).
    """
```

### 5.2 JavaScript (Frontend)

- Vanilla JS only — no frameworks, no npm, no build step
- ES6+ syntax (const, let, arrow functions, template literals)
- All data fetched once on page load, stored in a module-level array
- Filter operations use `.filter()` on that array — no DOM queries in filter logic
- Use `const` by default, `let` only when reassignment is needed

### 5.3 HTML/CSS

- Semantic HTML5 elements (`main`, `section`, `article`, `footer`, `nav`)
- Plain CSS — no Tailwind, no Bootstrap, no external CSS frameworks
- External links must always have `rel="noopener noreferrer"` and `target="_blank"`
- Mobile-friendly — use CSS flexbox or grid

---

## 6. Environment Variables

All configuration must come from environment variables. Never hardcode values.

Required variables (defined in `.env`, documented in `.env.example`):

```bash
# Application
USER_AGENT=DevOpsJobsPortal/1.0 (personal project; contact: your@email.com)
DB_PATH=./data/jobs.db
LOG_RETENTION_DAYS=30

# API
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_ORIGIN=http://localhost:3000   # Update to Netlify URL in production

# Scraper
SCRAPE_SCHEDULE=0 1 * * *              # 1AM UTC = 6AM IST
```

The `.env` file must never be committed to Git. It is in `.gitignore`.
Only `.env.example` (with placeholder values, no secrets) is committed.

---

## 7. Testing Standards

- Write tests in `backend/tests/`
- Use `pytest`
- Test file naming: `test_<module_name>.py`
- Every function in `filters.py` and `tagger.py` must have at least one test
- Run tests before pushing: `pytest backend/tests/`
- Tests must pass before a PR is opened

---

## 8. Task Reference

All tasks are defined in `docs/tasks.md`. Before starting any session:

1. Ask the user which task they want to work on
2. Read the task description from `docs/tasks.md`
3. Check dependencies — confirm dependent tasks are complete
4. Create the correct feature branch
5. Complete the task
6. Push and remind user to open PR

---

## 9. Things to Never Do

| Action | Reason |
|---|---|
| Push to `main` directly | Branch protection — will be rejected anyway |
| Push to `develop` directly | All work goes through feature branches |
| Hardcode API URLs or config values | Must be in env vars or config files |
| Make HTTP requests without User-Agent header | Violates source API compliance rules |
| Trigger scraper from a web request | Scraper and frontend are fully decoupled |
| Add Working Nomads as a source | No confirmed free public API |
| Use an ORM in Phase 1 | Plain sqlite3 only — keep it simple |
| Use a JS framework | Vanilla JS only in Phase 1 |
| Commit the `.env` file | Contains secrets — always gitignored |
| Use vague commit messages | Every commit must describe what changed |

---

## 10. How to Start a Session

When Claude Code starts a new session on this project, always:

1. Read this file (`CLAUDE.md`) fully
2. Run `git branch` — confirm you are on a feature branch
3. Run `git status` — understand current state
4. Ask the user: *"Which task from tasks.md would you like to work on?"*
5. Read that task's description in `docs/tasks.md`
6. Confirm dependencies are met
7. Create the feature branch if not already on one
8. Begin work

---

**This file was created as part of TASK-001.**
**Do not modify this file without explicit instruction from the user.**

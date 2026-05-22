# InfraJobs

A personal-use job aggregation portal for **DevOps, SRE, Platform Engineering, Cloud & Infrastructure** roles — India & Remote. Updated daily at 6AM IST. Jobs are pulled from 7 legal public sources once a day, cached in SQLite, and served through a FastAPI backend to a zero-framework HTML/CSS/JS frontend.

Built as both a daily job-search tool and a live portfolio infrastructure project.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SCRAPER  (Python)                          │
│  Runs once daily at 06:00 IST (00:30 UTC) via cron           │
│                                                              │
│  Source A — Open APIs          Source B — ATS                │
│  ├── RemoteOK                  ├── Greenhouse  (31 companies) │
│  ├── Remotive                  ├── Lever       (13 companies) │
│  ├── Jobicy                    └── Ashby       ( 9 companies) │
│  ├── Arbeitnow                                               │
│  └── HN Algolia (Who's Hiring)  companies.yaml  (config)     │
│                                                              │
│  keyword filter → normalise → location tag → write SQLite    │
└──────────────────────────┬───────────────────────────────────┘
                           │ SQLite file
┌──────────────────────────▼───────────────────────────────────┐
│                  BACKEND API  (FastAPI)                       │
│  GET /api/jobs   → reads SQLite → returns JSON               │
│  GET /api/health → last scrape status                        │
│  No write endpoints. No scraper trigger.                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ JSON over HTTP
┌──────────────────────────▼───────────────────────────────────┐
│           FRONTEND  (HTML + CSS + Vanilla JS)                 │
│  Loads once → fetches /api/jobs → renders cards              │
│  All 6 filters are client-side — no server round-trips       │
│  Page refresh = re-render from same cached response          │
└──────────────────────────────────────────────────────────────┘
```

---

## Sources & Compliance

| Source | Type | Calls/day | Attribution | Notes |
|---|---|---|---|---|
| RemoteOK | Open API | 1 | Per card → remoteok.com | User-Agent required |
| Remotive | Open API | 4 | Per card → remotive.com | Max 4/day; no email gating |
| Jobicy | Open API | 4 | Per card → jobicy.com | No redistribution |
| Arbeitnow | Open API | 1 (paginated) | Per card → arbeitnow.com | Link back required |
| HN Algolia | Open API | 2 | Per card → news.ycombinator.com | Who's Hiring thread only |
| Greenhouse | ATS | 1 per company | Per job → boards.greenhouse.io | Public API |
| Lever | ATS | 1 per company | Per job → jobs.lever.co | Public API |
| Ashby | ATS | 1 per company | Per job → jobs.ashbyhq.com | Public API |

Every HTTP request includes `User-Agent: InfraJobs/1.0 (personal project; contact: your@email.com)`.

---

## Running Locally

### Prerequisites

- Python 3.11+
- A terminal in the project root

### 1 — Clone and set up environment

```bash
git clone https://github.com/velanaren/devops-job-portal.git
cd devops-job-portal

cp .env.example .env
# Edit .env if needed — defaults work for local development
```

### 2 — Install backend dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3 — Initialise the database

```bash
# From inside backend/ with venv active
python3 -c "from db.database import init_db; init_db()"
```

### 4 — Run the scraper (populates the DB)

```bash
python3 -m scraper.main
```

Expected output:
```
============================================================
  Scraper run started — 2026-05-09 12:00:00 UTC
============================================================

[RemoteOK] Fetching...
[RemoteOK] SUCCESS — 14 jobs (1.2s)
[Remotive] Fetching...
...
============================================================
  Scraper run complete — 2026-05-09 12:05:30 UTC
  Total jobs written : 142
  Sources            : 8
============================================================
```

### 5 — Start the API server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify:
```bash
curl http://localhost:8000/api/jobs   | python3 -m json.tool | head -20
curl http://localhost:8000/api/health | python3 -m json.tool
```

### 6 — Open the frontend

Update `API_BASE_URL` in `frontend/app.js` if needed (default: `http://localhost:8000`), then open `frontend/index.html` directly in a browser.

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

68 tests across `test_filters.py` (37) and `test_tagger.py` (31). All must pass before opening a PR.

---

## Adding a New Company (Source B)

Edit `backend/config/companies.yaml` — no code changes required:

```yaml
companies:
  - name: Your Company
    ats: greenhouse        # greenhouse | lever | ashby
    slug: your-company     # slug used in the ATS API URL
```

Find the slug:
- **Greenhouse** — `boards.greenhouse.io/{slug}`
- **Lever** — `jobs.lever.co/{slug}`
- **Ashby** — `jobs.ashbyhq.com/{slug}`

Restart the scraper on the next daily run (or manually) — the new company is picked up automatically.

---

## Adding a New Source A Module

1. Create `backend/scraper/sources/your_source.py` following the existing pattern:

```python
SOURCE_NAME = "YourSource"
SOURCE_URL  = "https://yoursource.com"

HEADERS = {
    "User-Agent": USER_AGENT,   # from config.settings
    "Accept":     "application/json",
}

def fetch_jobs() -> list[dict]:
    """Fetch, filter, normalise, and return job dicts."""
    ...
```

2. Import and register in `backend/scraper/main.py`:

```python
from scraper.sources.your_source import fetch_jobs as fetch_your_source

SOURCES = [
    ...
    ("YourSource", fetch_your_source),
]
```

3. Add the source name to the filter dropdown in `frontend/index.html`.

That's it — the orchestrator, logger, and DB writes are handled automatically.

---

## Environment Variables

All config lives in `.env` (never committed). Copy from `.env.example`:

| Variable | Default | Description |
|---|---|---|
| `USER_AGENT` | `InfraJobs/1.0 ...` | Sent on every outbound HTTP request |
| `DB_PATH` | `./data/jobs.db` | SQLite database file path |
| `LOG_RETENTION_DAYS` | `30` | Days to keep scrape log entries |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | Allowed CORS origin — set to Netlify URL in production |
| `SCRAPE_SCHEDULE` | `0 1 * * *` | Cron expression (1AM UTC = 6AM IST) |

---

## Project Structure

```
devops-job-portal/
├── backend/
│   ├── scraper/
│   │   ├── main.py              # Orchestrator — cron entry point
│   │   ├── filters.py           # Keyword filter, role type, experience level
│   │   ├── tagger.py            # Location priority tagger
│   │   ├── logger.py            # Scrape run DB logger
│   │   └── sources/
│   │       ├── remoteok.py      # Source A1
│   │       ├── remotive.py      # Source A2
│   │       ├── jobicy.py        # Source A3
│   │       ├── arbeitnow.py     # Source A4
│   │       ├── hn_algolia.py    # Source A5
│   │       └── ats/
│   │           ├── __init__.py  # load_companies(), strip_html()
│   │           ├── greenhouse.py  # Source B1
│   │           ├── lever.py       # Source B2
│   │           └── ashby.py       # Source B3
│   ├── api/
│   │   ├── main.py              # FastAPI app
│   │   └── models.py            # Pydantic response models
│   ├── db/
│   │   ├── database.py          # SQLite helpers
│   │   └── schema.sql           # Table definitions
│   ├── config/
│   │   ├── settings.py          # Env var loader
│   │   └── companies.yaml       # Source B company list
│   ├── tests/
│   │   ├── test_filters.py      # 37 tests
│   │   └── test_tagger.py       # 31 tests
│   └── requirements.txt
├── frontend/
│   ├── index.html               # Single page — semantic HTML5
│   ├── styles.css               # Dark/light mode, responsive grid
│   └── app.js                   # Fetch once, filter in memory
├── docs/
│   ├── requirements.md
│   ├── prd.md
│   └── tasks.md
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

---

## Phase 2 Roadmap

Phase 2 converts this into a production-grade, observable system on AWS — built entirely by the owner as the portfolio infrastructure component.

| Area | Technology |
|---|---|
| Containerisation | Docker (backend + frontend) |
| Orchestration | Kubernetes on AWS EKS |
| Database | RDS PostgreSQL (replacing SQLite) |
| Infrastructure | Terraform — VPC, EKS, RDS, ALB, Route53, ACM |
| CI/CD | GitHub Actions → ECR → EKS deploy |
| Observability | Prometheus + Grafana |
| Alerting | Alertmanager → Slack/email |
| SLOs | Scraper ≥95% success · Uptime ≥99.5% · API p99 <500ms |

See [`docs/tasks.md`](./docs/tasks.md) for the full task breakdown (TASK-026 through TASK-038).

---

## Docs

- [Requirements](./docs/requirements.md)
- [PRD](./docs/prd.md)
- [Tasks](./docs/tasks.md)

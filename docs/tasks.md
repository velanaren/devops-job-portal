# Task Breakdown
## InfraJobs — v1.0

---

## Overview

Tasks are organised into phases and epics. Each task has an ID, owner, description, dependencies, and acceptance criteria.

**Owner legend:**
- 🤖 Claude — writes the code
- 👤 You — infra, config, deployment, observability

**Status values:** `[ ]` Not started | `[~]` In progress | `[x]` Done

---

## Phase 1 — Build & Deploy

### Epic 1: Project Setup

---

**TASK-001**
**Owner:** 👤 You
**Title:** Create GitHub repository

```
- Create a new GitHub repo: devops-job-portal (or your preferred name)
- Initialise with README
- Create branch protection on main (require PR, no direct push)
- Create branches: main, develop
- Add .gitignore for Python and Node
```
**Depends on:** Nothing
**Acceptance:** Repo exists, branches created, .gitignore present

---

**TASK-002**
**Owner:** 🤖 Claude
**Title:** Scaffold project directory structure

```
devops-job-portal/
├── backend/
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── main.py              # Scraper entry point
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── remoteok.py
│   │   │   ├── remotive.py
│   │   │   ├── jobicy.py
│   │   │   ├── arbeitnow.py
│   │   │   ├── hn_algolia.py
│   │   │   └── ats/
│   │   │       ├── __init__.py
│   │   │       ├── greenhouse.py
│   │   │       ├── lever.py
│   │   │       └── ashby.py
│   │   ├── filters.py           # Keyword and role filters
│   │   ├── tagger.py            # Location priority tagger
│   │   └── logger.py            # Scrape run logger
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   └── models.py            # Pydantic models
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLite connection
│   │   └── schema.sql           # Table definitions
│   ├── config/
│   │   ├── companies.yaml       # Source B company list
│   │   └── settings.py          # Env var loader
│   ├── requirements.txt
│   └── Dockerfile               # Ready for Phase 2
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── Dockerfile               # Ready for Phase 2
├── docker-compose.yml           # Ready for Phase 2
├── .env.example
├── .gitignore
└── README.md
```
**Depends on:** TASK-001
**Acceptance:** Structure exists, all files created (empty stubs acceptable)

---

**TASK-003**
**Owner:** 🤖 Claude
**Title:** Create database schema and connection module

```
- Write schema.sql with jobs and scrape_logs tables (per PRD spec)
- Write database.py with:
  - SQLite connection helper
  - Table initialisation function
  - Insert job function (upsert-safe)
  - Insert scrape log function
  - Query jobs function (with 7-day TTL filter)
  - Query health function
```
**Depends on:** TASK-002
**Acceptance:** `python -c "from db.database import init_db; init_db()"` creates DB with correct schema

---

**TASK-004**
**Owner:** 🤖 Claude
**Title:** Create settings and config loader

```
- Write settings.py to load from environment variables:
  - USER_AGENT string
  - SCRAPE_SCHEDULE (cron expression)
  - DB_PATH
  - LOG_RETENTION_DAYS
- Write companies.yaml with initial company list:
  - All companies from platformengineeringcareers.com/india
    that use Greenhouse, Lever, or Ashby
  - Additional: Cloudflare, Datadog, Grafana Labs, PagerDuty,
    HashiCorp, Fastly, Honeycomb, Sentry, Temporal
- Write .env.example with all required vars
```
**Depends on:** TASK-002
**Acceptance:** settings.py loads without error; companies.yaml has valid YAML structure

---

### Epic 2: Scraper — Source A

---

**TASK-005**
**Owner:** 🤖 Claude
**Title:** Build RemoteOK scraper module

```
Compliance:
- User-Agent header on every request
- Fetch once; do not retry excessively
- Link back to RemoteOK in source_url field

Logic:
- GET https://remoteok.com/api
- Filter jobs by keyword list (filters.py)
- Map fields to DB schema
- Tag location_tag via tagger.py
- Return list of normalised job dicts
- Log success/failure to scrape_logs
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module returns ≥1 job when run manually; log entry written; no extra HTTP calls

---

**TASK-006**
**Owner:** 🤖 Claude
**Title:** Build Remotive scraper module

```
Compliance:
- User-Agent header on every request
- Never exceed 4 calls/day (daily cron = 1 call — safe)
- Link back to Remotive per job card
- Do not gate jobs behind email/signup

Logic:
- GET https://remotive.com/api/remote-jobs?search=devops
- Also fetch: sre, platform+engineer, cloud+engineer, tech+support
  (multiple calls within same daily run — total ≤ 4)
- Filter, normalise, tag
- Return normalised job dicts
- Log result
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module returns jobs; stays within 4-call limit per run; compliance fields populated

---

**TASK-007**
**Owner:** 🤖 Claude
**Title:** Build Jobicy scraper module

```
Compliance:
- User-Agent header
- Max 1 call per hour — daily cron = 1 call — safe
- Attribute Jobicy on every card
- Do not redistribute to other platforms

Logic:
- GET https://jobicy.com/api/v2/remote-jobs?tag=devops&count=100
- Also: tag=sre, tag=platform-engineer, tag=cloud-engineer (1 call each)
- Total calls within daily run ≤ 4 (1 per keyword) — safe
- Filter, normalise, tag
- Log result
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module returns jobs; call count ≤ 4; attribution fields populated

---

**TASK-008**
**Owner:** 🤖 Claude
**Title:** Build Arbeitnow scraper module

```
Compliance:
- User-Agent header
- Provide link back to Arbeitnow
- Respectful fetch — 1 call per day

Logic:
- GET https://www.arbeitnow.com/api/job-board-api?remote=true
- Paginate if needed (check if results are paginated)
- Filter by keyword
- Normalise and tag
- Log result
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module returns jobs; link back to Arbeitnow in source_url

---

**TASK-009**
**Owner:** 🤖 Claude
**Title:** Build HN Algolia scraper module

```
Compliance:
- Credit Hacker News as source
- 1 call per day — safe
- Only search "Who is Hiring" thread

Logic:
- Find current month's "Ask HN: Who is Hiring?" thread ID
  via: GET https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+Hiring&tags=story
- Search comments in that thread:
  GET https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&query=devops+remote
- Parse job details from comment text (best-effort parsing)
- Normalise to DB schema
- Tag: most HN jobs = Remote Global
- Log result
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module finds current HN thread; returns parsed job comments

---

### Epic 3: Scraper — Source B (ATS)

---

**TASK-010**
**Owner:** 🤖 Claude
**Title:** Build Greenhouse ATS scraper module

```
Logic:
- Load companies.yaml → filter where ats == "greenhouse"
- For each company slug:
  GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
- Filter returned jobs by keyword list
- Extract: title, location, apply_url, posted_date, content (for skills)
- source_url = https://boards.greenhouse.io/{slug}
- Normalise and tag location
- Log per-company result
- Sleep 1 second between company calls (respectful)
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module iterates all Greenhouse companies; filters correctly; 1s delay between calls

---

**TASK-011**
**Owner:** 🤖 Claude
**Title:** Build Lever ATS scraper module

```
Logic:
- Load companies.yaml → filter where ats == "lever"
- For each company slug:
  GET https://api.lever.co/v0/postings/{slug}?mode=json
- Filter by keyword list
- Extract: text (title), categories.location, hostedUrl (apply_url),
  createdAt (posted_date), additional (skills)
- source_url = https://jobs.lever.co/{slug}
- Normalise, tag, log
- Sleep 1 second between company calls
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module iterates Lever companies; correct field mapping; delay present

---

**TASK-012**
**Owner:** 🤖 Claude
**Title:** Build Ashby ATS scraper module

```
Logic:
- Load companies.yaml → filter where ats == "ashby"
- For each company slug:
  GET https://jobs.ashbyhq.com/api/non-authenticated-open-job-listings/{slug}
- Filter by keyword list
- Extract: title, location, jobUrl (apply_url), publishedDate, department
- source_url = https://jobs.ashbyhq.com/{slug}
- Normalise, tag, log
- Sleep 1 second between company calls
```
**Depends on:** TASK-003, TASK-004
**Acceptance:** Module iterates Ashby companies; correct field mapping; delay present

---

### Epic 4: Filters, Tagger & Normaliser

---

**TASK-013**
**Owner:** 🤖 Claude
**Title:** Build keyword filter module (filters.py)

```
- Define KEYWORD_LIST (from requirements section 5.2)
- Define ROLE_TYPE_MAP:
    devops → [devops, dev ops, devsecops]
    sre → [sre, site reliability]
    platform → [platform engineer, platform engineering]
    cloud → [cloud engineer, cloud infrastructure]
    appsupport → [application support, app support]
    techsupport → [tech support, technical support, l1, l2, l3]
- Function: matches_keyword(title, description) → bool
- Function: detect_role_type(title) → str
- Function: detect_experience_level(title, description) → str
    (entry / mid / senior / staff — based on keyword heuristics)
```
**Depends on:** TASK-002
**Acceptance:** Unit tests pass for all role type and keyword detections

---

**TASK-014**
**Owner:** 🤖 Claude
**Title:** Build location tagger module (tagger.py)

```
- Function: tag_location(location_raw, source_name) → str
  Logic:
    - If source in [RemoteOK, Remotive, Jobicy] → default "Remote Global"
      unless location_raw indicates a specific country
    - "anywhere" / "worldwide" / "work from anywhere" → Remote Global
    - "india" + "remote" → Remote India
    - "chennai" → Chennai
    - "bengaluru" / "bangalore" → Bengaluru
    - Else → Other
```
**Depends on:** TASK-002
**Acceptance:** Unit tests pass for all location tagging scenarios

---

### Epic 5: Scraper Orchestrator

---

**TASK-015**
**Owner:** 🤖 Claude
**Title:** Build scraper main orchestrator (scraper/main.py)

```
- Import all source modules
- Run each source in sequence within try/except
- Write results to DB via database.py
- Write scrape_logs entry for each source
- Write summary log: run start, per-source count, total, run end
- Entry point: callable as `python -m scraper.main`
- Must NOT be triggered by any web request
- Must be safe to run multiple times (idempotent writes)
```
**Depends on:** TASK-005 through TASK-014
**Acceptance:** Running `python -m scraper.main` fetches all sources, writes to DB, logs correctly

---

### Epic 6: Backend API

---

**TASK-016**
**Owner:** 🤖 Claude
**Title:** Build FastAPI backend (api/main.py)

```
Endpoints:
  GET /api/jobs
    - Query DB for jobs where TTL ≤ 7 days
    - Return JSON per PRD spec (section 3.4)
    - Include total count and fetched_at timestamp

  GET /api/health
    - Return last scrape run status per source
    - Return total jobs in DB
    - Return last run timestamp

CORS:
  - Allow requests from frontend origin (Netlify URL in Phase 1)

No write endpoints.
No scraper trigger endpoints.
```
**Depends on:** TASK-003
**Acceptance:** `curl localhost:8000/api/jobs` returns valid JSON; `curl localhost:8000/api/health` returns status

---

### Epic 7: Frontend

---

**TASK-017**
**Owner:** 🤖 Claude
**Title:** Build frontend HTML structure (index.html)

```
- Single HTML file
- Header: portal name, last updated timestamp
- Filter bar: all 6 filters as dropdowns
- Job count display ("X jobs found")
- Clear all filters button
- Job cards container (populated by JS)
- Footer: attribution statement + source list with links
- No framework — plain HTML only
- Semantic HTML (main, section, article, footer)
```
**Depends on:** TASK-002
**Acceptance:** Valid HTML; renders correctly in browser with empty job list

---

**TASK-018**
**Owner:** 🤖 Claude
**Title:** Build frontend styles (styles.css)

```
- Clean, professional design
- Dark/light mode support (prefers-color-scheme)
- Responsive — works on desktop and tablet
- Job card layout: clear hierarchy of title → company → meta → skills → apply
- Location badge colour coding:
    🌍 Remote Global → green
    🇮🇳 Remote India → blue
    📍 City → orange
- Filter bar stays visible while scrolling (sticky)
- Apply button: prominent, right-aligned on card
- Source attribution: subtle but present on every card
- No external CSS frameworks — plain CSS only
```
**Depends on:** TASK-017
**Acceptance:** Visually clean; responsive; badges colour-coded correctly

---

**TASK-019**
**Owner:** 🤖 Claude
**Title:** Build frontend JavaScript (app.js)

```
On load:
  - Fetch GET /api/jobs once
  - Store full job list in memory (JS array)
  - Render all job cards
  - Display last updated time from API response
  - Show total job count

Filter logic:
  - Attach event listeners to all filter dropdowns
  - On any filter change:
    - Apply all active filters using AND logic to in-memory array
    - Re-render filtered job cards
    - Update job count
  - "Clear all filters" resets all dropdowns and re-renders all jobs

Card render:
  - Generate HTML for each job
  - Location badge with correct colour
  - Source as attribution link (opens in new tab, noopener noreferrer)
  - Apply button (opens in new tab, noopener noreferrer)
  - Relative time display ("2 days ago")

No page reload on any user interaction.
```
**Depends on:** TASK-017, TASK-018
**Acceptance:** Filters work without page reload; apply link opens original URL; card count updates correctly

---

### Epic 8: Deployment — Phase 1

---

**TASK-020**
**Owner:** 👤 You
**Title:** Set up Render account and deploy backend

```
- Create account at render.com
- Create a new Web Service
- Connect GitHub repo
- Configure:
    Root directory: backend/
    Build command: pip install -r requirements.txt
    Start command: uvicorn api.main:app --host 0.0.0.0 --port 8000
- Add environment variables from .env.example
- Verify GET /api/jobs responds
- Verify GET /api/health responds
- Note the Render URL (needed for TASK-021 and TASK-022)
```
**Depends on:** TASK-016
**Acceptance:** API is live at Render URL; both endpoints return valid JSON

---

**TASK-021**
**Owner:** 👤 You
**Title:** Set up cron job on Render for daily scraper

```
- In Render dashboard → Cron Jobs → New Cron Job
- Connect same GitHub repo
- Command: python -m scraper.main
- Schedule: 0 1 * * *  (1AM UTC = 6AM IST)
- Add same environment variables
- Trigger manual run to verify
- Check scrape_logs table for run record
```
**Depends on:** TASK-015, TASK-020
**Acceptance:** Manual trigger succeeds; scrape_logs shows run record; jobs appear in DB

---

**TASK-022**
**Owner:** 👤 You
**Title:** Deploy frontend to Netlify

```
- Update app.js: set API_BASE_URL to Render backend URL
- Create account at netlify.com
- Drag and drop frontend/ folder to Netlify
  OR connect GitHub repo and set publish directory to frontend/
- Verify page loads with jobs from API
- Verify filters work
- Verify apply links open correctly
```
**Depends on:** TASK-019, TASK-020
**Acceptance:** Portal live on Netlify URL; displays jobs; filters functional; apply links work

---

**TASK-023**
**Owner:** 🤖 Claude
**Title:** Write README.md

```
Sections:
- What this is
- Architecture diagram (ASCII)
- Sources used + compliance summary
- How to run locally
- How to add a new company to companies.yaml
- How to add a new Source A module
- Environment variables reference
- Phase 2 roadmap
```
**Depends on:** All Phase 1 tasks complete
**Acceptance:** README renders correctly on GitHub; local run instructions work

---

### Epic 9: Testing & Validation

---

**TASK-024**
**Owner:** 🤖 Claude
**Title:** Write unit tests for filters and tagger

```
Tests for filters.py:
  - matches_keyword: positive and negative cases
  - detect_role_type: all 6 role types
  - detect_experience_level: all 4 levels

Tests for tagger.py:
  - Remote Global detection (source-based and keyword-based)
  - Remote India detection
  - Chennai detection
  - Bengaluru detection
  - Other fallback

Framework: pytest
Run with: pytest backend/tests/
```
**Depends on:** TASK-013, TASK-014
**Acceptance:** All tests pass; ≥80% function coverage on filters.py and tagger.py

---

**TASK-025**
**Owner:** 👤 You
**Title:** End-to-end validation checklist

```
Run through each item and mark complete:

[ ] Page loads in < 3 seconds (check DevTools Network tab)
[ ] Page refresh does NOT trigger any API call to source platforms
      (check Network tab — only /api/jobs should appear)
[ ] All 6 filters work correctly
[ ] Filter combinations (AND logic) work correctly
[ ] "Clear all filters" resets everything
[ ] Job count updates on filter change
[ ] Apply button opens original URL in new tab
[ ] Source attribution link is present on every card
[ ] Location badges show correct colour per type
[ ] Default sort is Remote Global first
[ ] Scraper logs show successful run
[ ] Jobs from all 8 sources appear in DB
[ ] Manual DB query confirms 7-day TTL filter works
```
**Depends on:** TASK-022
**Acceptance:** All checklist items marked complete

---

## Phase 2 — Infra, Observability & Portfolio (Owner-Built)

> These tasks are executed by you. Claude can assist with code/config as needed.

---

### Epic 10: Containerisation

**TASK-026**
**Owner:** 👤 You (🤖 Claude assists)
**Title:** Write Dockerfile for backend

```
- Base image: python:3.11-slim
- Copy requirements.txt and install dependencies
- Copy backend/ source
- Expose port 8000
- CMD: uvicorn api.main:app
- Build and test locally: docker build + docker run
```
**Depends on:** Phase 1 complete
**Acceptance:** `docker build` succeeds; container serves API correctly on localhost:8000

---

**TASK-027**
**Owner:** 👤 You (🤖 Claude assists)
**Title:** Write Dockerfile for frontend

```
- Base image: nginx:alpine
- Copy frontend/ into nginx html directory
- Copy custom nginx.conf (handle SPA routing if needed)
- Expose port 80
- Build and test locally
```
**Depends on:** Phase 1 complete
**Acceptance:** `docker build` succeeds; nginx serves frontend correctly

---

**TASK-028**
**Owner:** 👤 You (🤖 Claude assists)
**Title:** Write docker-compose.yml for local development

```
Services:
  backend:
    build: ./backend
    ports: 8000:8000
    env_file: .env
    volumes: ./data:/data  (for SQLite persistence)

  frontend:
    build: ./frontend
    ports: 80:80
    depends_on: backend

  scraper:
    build: ./backend
    command: python -m scraper.main
    env_file: .env
    profiles: ["scraper"]  (run manually: docker compose --profile scraper up)
```
**Depends on:** TASK-026, TASK-027
**Acceptance:** `docker compose up` starts both services; full portal works locally

---

### Epic 11: AWS Infrastructure (Terraform)

**TASK-029**
**Owner:** 👤 You
**Title:** Provision AWS base infrastructure with Terraform

```
Resources:
  - VPC with public and private subnets (2 AZs)
  - Internet Gateway
  - NAT Gateway
  - Route tables
  - Security groups
  - ECR repository (for Docker images)

State:
  - S3 bucket for Terraform state
  - DynamoDB table for state locking
```
**Depends on:** TASK-028
**Acceptance:** `terraform apply` completes; VPC and ECR exist in AWS console

---

**TASK-030**
**Owner:** 👤 You
**Title:** Provision EKS cluster with Terraform

```
Resources:
  - EKS cluster (managed node group)
  - Node group: t3.small × 2 (cost-conscious)
  - IAM roles for cluster and nodes
  - kubectl config update
  - Verify: kubectl get nodes
```
**Depends on:** TASK-029
**Acceptance:** EKS cluster active; nodes Ready in kubectl output

---

**TASK-031**
**Owner:** 👤 You
**Title:** Provision RDS PostgreSQL with Terraform

```
Resources:
  - RDS instance: db.t3.micro (PostgreSQL 15)
  - Private subnet placement
  - Security group: allow only from EKS node group
  - Secrets Manager entry for DB credentials
  - Update backend to use PostgreSQL (SQLAlchemy)
```
**Depends on:** TASK-030
**Acceptance:** RDS available; backend connects to PostgreSQL; existing data migrated

---

**TASK-032**
**Owner:** 👤 You
**Title:** Provision ALB, Route53, and ACM with Terraform

```
Resources:
  - Application Load Balancer
  - Target group for backend pods
  - ACM certificate for custom domain
  - Route53 hosted zone and A record
  - HTTPS listener on ALB
  - HTTP → HTTPS redirect
```
**Depends on:** TASK-030
**Acceptance:** Portal accessible at https://yourdomain.com over HTTPS

---

### Epic 12: CI/CD Pipeline

**TASK-033**
**Owner:** 👤 You (🤖 Claude assists)
**Title:** Set up GitHub Actions CI/CD pipeline

```
Triggers:
  - Push to main → full pipeline
  - Push to develop → test only

Pipeline steps:
  1. Run pytest (unit tests)
  2. Build Docker images (backend + frontend)
  3. Push to ECR
  4. Deploy to EKS (kubectl apply or Helm)

Scraper cron:
  - Kubernetes CronJob: 0 1 * * * (1AM UTC = 6AM IST)
  - Runs scraper container as a Job
```
**Depends on:** TASK-030, TASK-031
**Acceptance:** Push to main triggers pipeline; deployment visible in EKS; scraper CronJob scheduled

---

### Epic 13: Observability Stack

**TASK-034**
**Owner:** 👤 You (🤖 Claude assists)
**Title:** Add /metrics endpoint to backend (Prometheus)

```
- Install prometheus-client Python library
- Expose metrics at GET /metrics
- Implement counters/gauges from PRD section 5.4:
    scraper_run_total
    scraper_run_success_total
    scraper_run_failure_total
    scraper_jobs_fetched_total (labelled by source)
    scraper_source_duration_seconds (labelled by source)
    api_requests_total
    api_response_duration_seconds
    jobs_in_db_total
    jobs_expired_total
```
**Depends on:** TASK-030
**Acceptance:** `curl /metrics` returns Prometheus-format output with all defined metrics

---

**TASK-035**
**Owner:** 👤 You
**Title:** Deploy Prometheus to EKS

```
- Install via Helm: prometheus-community/kube-prometheus-stack
- Configure scrape job targeting backend /metrics
- Configure scrape job targeting Kubernetes system metrics
- Verify targets are UP in Prometheus UI
```
**Depends on:** TASK-034
**Acceptance:** All scrape targets green in Prometheus UI; metrics visible in query browser

---

**TASK-036**
**Owner:** 👤 You
**Title:** Build Grafana dashboards

```
Dashboard 1: Scraper Health
  - Scraper runs per day (bar chart)
  - Success vs failure rate (pie chart)
  - Jobs fetched per source per day (stacked bar)
  - Per-source fetch duration (histogram)
  - Last successful run timestamp (stat panel)

Dashboard 2: API Performance
  - Request rate (requests/min)
  - p50 / p95 / p99 latency
  - Error rate
  - Jobs in DB over time (line chart)
  - Jobs expired per day (counter)

Dashboard 3: Infrastructure
  - EKS node CPU and memory
  - Pod health
  - RDS connections and query time
```
**Depends on:** TASK-035
**Acceptance:** All 3 dashboards render with live data; no broken panels

---

**TASK-037**
**Owner:** 👤 You
**Title:** Configure Alertmanager rules

```
Alerts:
  - ScraperNotRun: no successful scraper run in 25 hours → critical
  - SourceConsecutiveFailures: any source fails 3 days in a row → warning
  - APIHighLatency: p99 > 1s for 5 minutes → warning
  - JobsDBEmpty: jobs_in_db_total == 0 → critical
  - PodCrashLooping: pod restarts > 5 in 10 minutes → warning

Receivers:
  - Email or Slack webhook (your choice)
```
**Depends on:** TASK-035
**Acceptance:** Manually trigger a condition → verify alert fires and notification received

---

**TASK-038**
**Owner:** 👤 You
**Title:** Define and document SLOs

```
Create slo.md document:
  - Scraper success rate SLO: ≥ 95% over 30 days
  - Page availability SLO: ≥ 99.5% over 30 days
  - API p99 latency SLO: < 500ms
  - Data freshness SLO: updated by 7AM IST daily

Create Grafana SLO dashboards:
  - Error budget burn rate
  - SLO compliance status
  - Historical SLO achievement
```
**Depends on:** TASK-036
**Acceptance:** SLO document exists; Grafana shows SLO compliance for all 4 SLOs

---

## Task Summary

| Phase | Epic | Tasks | Owner |
|---|---|---|---|
| Phase 1 | Project Setup | TASK-001 to TASK-004 | Mixed |
| Phase 1 | Scraper Source A | TASK-005 to TASK-009 | 🤖 Claude |
| Phase 1 | Scraper Source B | TASK-010 to TASK-012 | 🤖 Claude |
| Phase 1 | Filters & Tagger | TASK-013 to TASK-014 | 🤖 Claude |
| Phase 1 | Orchestrator | TASK-015 | 🤖 Claude |
| Phase 1 | Backend API | TASK-016 | 🤖 Claude |
| Phase 1 | Frontend | TASK-017 to TASK-019 | 🤖 Claude |
| Phase 1 | Deployment | TASK-020 to TASK-023 | 👤 You |
| Phase 1 | Testing | TASK-024 to TASK-025 | Mixed |
| Phase 2 | Containerisation | TASK-026 to TASK-028 | 👤 You |
| Phase 2 | AWS Infra | TASK-029 to TASK-032 | 👤 You |
| Phase 2 | CI/CD | TASK-033 | 👤 You |
| Phase 2 | Observability | TASK-034 to TASK-038 | 👤 You |

**Total tasks:** 38
**Phase 1 tasks:** 25
**Phase 2 tasks:** 13
**Claude-owned:** 18
**You-owned:** 14
**Shared:** 6

---

## Suggested Execution Order

```
Week 1:
  TASK-001 → TASK-002 → TASK-003 → TASK-004
  → TASK-013 → TASK-014 (filters + tagger)
  → TASK-024 (tests for filters)

Week 2:
  TASK-005 → TASK-006 → TASK-007 → TASK-008 → TASK-009 (Source A)
  → TASK-010 → TASK-011 → TASK-012 (Source B)
  → TASK-015 (orchestrator)

Week 3:
  TASK-016 (API)
  → TASK-017 → TASK-018 → TASK-019 (frontend)
  → TASK-023 (README)

Week 3-4:
  TASK-020 → TASK-021 → TASK-022 (deployment)
  → TASK-025 (validation)

Phase 2 — ongoing:
  TASK-026 → TASK-027 → TASK-028 (Docker)
  → TASK-029 → TASK-030 → TASK-031 → TASK-032 (AWS)
  → TASK-033 (CI/CD)
  → TASK-034 → TASK-035 → TASK-036 → TASK-037 → TASK-038 (Observability)
```

---

**Document version:** 1.0
**Status:** Ready for execution — start with TASK-001

# Product Requirements Document (PRD)
## DevOps Job Portal — v1.0

---

## 1. Product Overview

### 1.1 Product Name
DevOps Job Portal (working title)

### 1.2 Product Summary
A single-page, no-login job aggregation portal for DevOps, SRE, Platform, Cloud, Application Support, and Tech Support roles. Jobs are sourced legally from public APIs and ATS platforms, refreshed once daily at 6AM IST, and served from a cache. The user visits the portal to browse and filter fresh listings and clicks through to apply on the original source.

### 1.3 Problem Statement
Finding relevant DevOps/SRE/Platform roles requires checking multiple job boards, ATS portals, and company career pages manually every day. There is no single, focused, noise-free aggregator that prioritises remote roles for an India-based senior engineer, surfaces curated company listings from known DevOps hirers, and does so legally without requiring logins or paywalls.

### 1.4 Solution
A self-hosted, automated job portal that:
- Pulls from 5 open APIs and 3 ATS platforms daily
- Filters for DevOps/SRE/Platform/Support roles automatically
- Prioritises remote-first listings
- Requires no login, no payment, no tracking
- Acts as a live portfolio project for infra and observability work

### 1.5 Goals

| Goal | Metric |
|---|---|
| Personal job search utility | Owner uses it daily during job search |
| Legal compliance | Zero ToS violations across all sources |
| Portfolio value | Deployed publicly with observable infra by Phase 2 |
| Low maintenance | < 30 min/week to maintain after launch |

---

## 2. User Stories

### Epic 1: Daily Job Discovery

**US-01**
> As a job seeker, I want to open the portal and immediately see today's fresh job listings without doing anything, so that I can start my daily job search instantly.

Acceptance criteria:
- Page loads with cached data from the most recent 6AM fetch
- No login, no CAPTCHA, no friction
- Jobs are visible within 3 seconds of page load

---

**US-02**
> As a job seeker, I want remote jobs to appear at the top of the list by default, so that my highest-priority roles are immediately visible.

Acceptance criteria:
- Default sort: Remote Global → Remote India → Chennai → Bengaluru → Other
- Location badge is visible on each card
- Sort is applied without any user action

---

**US-03**
> As a job seeker, I want to see only jobs posted in the last 7 days, so that I am not wasting time on stale listings.

Acceptance criteria:
- Jobs older than 7 days do not appear on the page
- Expiry is silent — no messaging about removed jobs
- TTL is based on posted date from source; fetched date used as fallback

---

**US-04**
> As a job seeker, I want each job card to show the title, company, location, skills, experience level, source, and a direct apply link, so that I can evaluate and act on a job without leaving the portal.

Acceptance criteria:
- All 8 fields present on every card
- Apply button opens original posting in new tab
- Source is a clickable attribution link

---

### Epic 2: Filtering & Discovery

**US-05**
> As a job seeker, I want to filter jobs by role type, so that I can narrow down to DevOps only or SRE only when I want to focus.

Acceptance criteria:
- Role type filter with options: DevOps, SRE, Platform Engineer, Application Support, Tech Support, Cloud Engineer, All
- Filter applies instantly without page reload
- Job count updates to reflect filtered results

---

**US-06**
> As a job seeker, I want to filter by location priority, so that I can focus on Remote Global when I'm in the mood to apply internationally.

Acceptance criteria:
- Location priority filter: Remote Global, Remote India, Chennai, Bengaluru, Other, All
- Works in combination with other filters

---

**US-07**
> As a job seeker, I want to filter by how recently a job was posted, so that I can find the freshest listings when time is limited.

Acceptance criteria:
- "Posted within" filter: Last 24hrs, Last 3 days, Last 7 days
- Defaults to Last 7 days on load

---

**US-08**
> As a job seeker, I want to filter by job source, so that I can see only Greenhouse/Lever jobs from my curated company list when I want to target specific companies.

Acceptance criteria:
- Source filter: RemoteOK, Remotive, Jobicy, Arbeitnow, HN, Greenhouse, Lever, Ashby, All
- Works in combination with other filters

---

**US-09**
> As a job seeker, I want to reset all filters with one click, so that I can go back to the full list quickly.

Acceptance criteria:
- "Clear all filters" button visible when any filter is active
- Clicking it resets all filters to default
- Job count returns to total

---

### Epic 3: Trust & Transparency

**US-10**
> As a job seeker, I want to see where each job came from, so that I know the listing is legitimate and can verify it.

Acceptance criteria:
- Source name displayed on every card as a clickable link
- Link goes to the source platform (not just the homepage — ideally the specific listing)

---

**US-11**
> As a job seeker, I want the Apply button to take me directly to the original job posting, so that I am never confused about where I am applying.

Acceptance criteria:
- Apply button opens original URL in new tab
- `rel="noopener noreferrer"` on all external links
- No intermediary pages or redirects within the portal

---

### Epic 4: Data Freshness (Background — Not User-Facing)

**US-12**
> As the portal owner, I want the scraper to run automatically at 6AM IST every day, so that fresh data is available when I open the portal in the morning.

Acceptance criteria:
- Cron job triggers at 06:00 IST (00:30 UTC)
- Scraper fetches all sources in sequence
- Data is written to the database on completion
- Page serves updated data on next load — no manual intervention needed

---

**US-13**
> As the portal owner, I want the scraper to fail gracefully if one source is down, so that a single source outage does not break the entire feed.

Acceptance criteria:
- Per-source try/except handling
- Failed source is logged with timestamp + error
- Remaining sources continue to fetch
- Previous data for the failed source is retained

---

**US-14**
> As the portal owner, I want a scraper run log, so that I can debug issues and verify the feed is healthy.

Acceptance criteria:
- Log file (or stdout) captures: run start time, per-source fetch status, job count per source, run end time, total jobs stored
- Logs retained for 30 days

---

## 3. Functional Specification

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    SCRAPER (Python)                      │
│  Runs once daily at 6AM IST via cron                     │
│                                                          │
│  Source A                    Source B                    │
│  ├── RemoteOK API            ├── Greenhouse API          │
│  ├── Remotive API            ├── Lever API               │
│  ├── Jobicy API              └── Ashby API               │
│  ├── Arbeitnow API                                       │
│  └── HN Algolia API          companies.yaml (config)     │
│                                                          │
│  Keyword filter → Normalise → Write to SQLite DB         │
└───────────────────────┬─────────────────────────────────┘
                        │ SQLite file
┌───────────────────────▼─────────────────────────────────┐
│                 BACKEND API (FastAPI)                     │
│  GET /api/jobs  → reads from SQLite → returns JSON       │
│  No write endpoints exposed                              │
└───────────────────────┬─────────────────────────────────┘
                        │ JSON over HTTP
┌───────────────────────▼─────────────────────────────────┐
│              FRONTEND (HTML + CSS + Vanilla JS)          │
│  Loads once → fetches /api/jobs → renders job cards      │
│  All filtering is client-side                            │
│  Page refresh = re-render from same cached API response  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Scraper Specification

#### 3.2.1 Execution Model
- Triggered by cron at 06:00 IST (00:30 UTC)
- Sequential fetch — one source at a time
- Total expected runtime: under 30 minutes
- Single process, no parallelism required in Phase 1

#### 3.2.2 Keyword Filter
Jobs are included only if their title or description contains at least one keyword from:

```
devops, dev ops, sre, site reliability, platform engineer,
infrastructure engineer, infra engineer, cloud engineer,
application support, app support, tech support, technical support,
l1 support, l2 support, l3 support, systems engineer,
operations engineer, release engineer, build engineer
```

#### 3.2.3 Location Priority Tagging Logic

| Tag | Detection Logic |
|---|---|
| Remote Global | Source is RemoteOK/Remotive/Jobicy (remote-only boards), OR location field contains "anywhere", "worldwide", "global", "remote" with no country restriction |
| Remote India | Location contains "india" AND "remote", OR ATS job tagged remote with India location |
| Chennai | Location contains "chennai" |
| Bengaluru | Location contains "bengaluru", "bangalore" |
| Other | None of the above |

#### 3.2.4 Source B Company Config (`companies.yaml`)
```yaml
companies:
  - name: Cloudflare
    ats: greenhouse
    slug: cloudflare

  - name: Datadog
    ats: greenhouse
    slug: datadog

  - name: Grafana Labs
    ats: lever
    slug: grafanalabs

  - name: PagerDuty
    ats: greenhouse
    slug: pagerduty

  # ... 108+ companies from platformengineeringcareers.com/india
  # ... additional well-known DevOps hirers
```

#### 3.2.5 HTTP Request Requirements
Every outbound request must include:
```
User-Agent: DevOpsJobsPortal/1.0 (personal project; contact: your@email.com)
Accept: application/json
```

#### 3.2.6 Error Handling Per Source
```
try:
  fetch source
  parse and filter jobs
  write to DB
  log: SUCCESS | source | job_count
except:
  log: FAILURE | source | error_message | http_status
  retain previous data for this source
  continue to next source
```

### 3.3 Database Schema (SQLite — Phase 1)

#### Table: `jobs`
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| title | TEXT | Job title |
| company | TEXT | Company name |
| location_raw | TEXT | Raw location string from source |
| location_tag | TEXT | Remote Global / Remote India / Chennai / Bengaluru / Other |
| job_type | TEXT | remote / hybrid / onsite |
| source_name | TEXT | RemoteOK / Remotive / Jobicy / Arbeitnow / HN / Greenhouse / Lever / Ashby |
| source_url | TEXT | Attribution URL for source platform |
| apply_url | TEXT | Original job posting URL |
| posted_date | DATE | Posted date from source (nullable) |
| fetched_date | DATE | Date scraper fetched this job |
| skills | TEXT | Comma-separated skills/tags |
| experience_level | TEXT | entry / mid / senior / staff |
| role_type | TEXT | devops / sre / platform / appsupport / techsupport / cloud |
| created_at | TIMESTAMP | DB insert timestamp |

#### Table: `scrape_logs`
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_date | DATE | Date of scrape run |
| source_name | TEXT | Source identifier |
| status | TEXT | success / failure |
| jobs_fetched | INTEGER | Count of jobs fetched |
| error_message | TEXT | Error detail if failure |
| http_status | INTEGER | HTTP status code if failure |
| duration_seconds | REAL | Time taken for this source |
| created_at | TIMESTAMP | Log entry timestamp |

### 3.4 API Specification (FastAPI)

#### `GET /api/jobs`
Returns all jobs within the 7-day TTL window.

Response:
```json
{
  "fetched_at": "2026-05-07T06:15:00",
  "total": 142,
  "jobs": [
    {
      "id": 1,
      "title": "Senior SRE",
      "company": "Cloudflare",
      "location_raw": "Remote",
      "location_tag": "Remote Global",
      "job_type": "remote",
      "source_name": "Greenhouse",
      "source_url": "https://boards.greenhouse.io/cloudflare",
      "apply_url": "https://boards.greenhouse.io/cloudflare/jobs/12345",
      "posted_date": "2026-05-05",
      "fetched_date": "2026-05-07",
      "skills": "kubernetes,terraform,prometheus",
      "experience_level": "senior",
      "role_type": "sre"
    }
  ]
}
```

#### `GET /api/health`
Returns scraper health status.

Response:
```json
{
  "status": "ok",
  "last_run": "2026-05-07T06:15:00",
  "last_run_status": "success",
  "sources": {
    "RemoteOK": "success",
    "Remotive": "success",
    "Jobicy": "failed",
    "Arbeitnow": "success",
    "HN": "success"
  }
}
```

### 3.5 Frontend Specification

#### Layout
```
┌────────────────────────────────────────────────┐
│  [Logo / Title]          Last updated: 6AM IST  │
├────────────────────────────────────────────────┤
│  FILTERS ROW                                    │
│  [Role ▼] [Location ▼] [Type ▼] [Source ▼]    │
│  [Experience ▼] [Posted Within ▼] [Clear All]  │
│  42 jobs found                                  │
├────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐  │
│  │ 🌍 Remote Global                         │  │
│  │ Senior SRE — Cloudflare                  │  │
│  │ 📍 Remote | ⏱ 2 days ago                │  │
│  │ Skills: kubernetes terraform prometheus  │  │
│  │ Experience: Senior | Source: Greenhouse  │  │
│  │                          [Apply →]       │  │
│  └──────────────────────────────────────────┘  │
│  ... more cards ...                             │
├────────────────────────────────────────────────┤
│  Footer: Jobs aggregated from public sources.   │
│  We do not own these listings.                  │
│  Sources: RemoteOK | Remotive | Jobicy | ...    │
└────────────────────────────────────────────────┘
```

#### Client-Side Filter Logic
- All job data fetched once on page load into a JS array
- Filters are applied as array `.filter()` operations in memory
- No server round-trip on filter change
- Job count updates after each filter operation

---

## 4. Source Compliance Summary

| Source | Fetch Limit | Attribution | Delay | Notes |
|---|---|---|---|---|
| RemoteOK | 1x/day | Per card | 24hr | User-Agent required |
| Remotive | Max 4x/day | Per card | 24hr | No email gating |
| Jobicy | Max 1x/hr | Per card | 6hr | No redistribution |
| Arbeitnow | Respectful | Per card | None | Link back required |
| HN Algolia | 1x/day | Per card | None | Who's Hiring only |
| Greenhouse | Respectful | Per job | None | Public API |
| Lever | Respectful | Per job | None | Public API |
| Ashby | Respectful | Per job | None | Public API |

---

## 5. Phase 2 — Infra & Observability (Owner-Built)

This section defines what the owner will build as the portfolio component. The application code remains unchanged; the infra around it changes.

### 5.1 Containerisation
- Dockerfile for backend (FastAPI + scraper)
- Dockerfile for frontend (nginx serving static files)
- docker-compose.yml for local development

### 5.2 AWS Infrastructure (Terraform)
- VPC with public and private subnets
- EKS cluster (Kubernetes)
- RDS PostgreSQL (replacing SQLite)
- ALB (Application Load Balancer)
- Route53 for DNS
- ACM for TLS/HTTPS
- S3 for static frontend assets
- IAM roles and policies

### 5.3 CI/CD (GitHub Actions)
- On push to `main`: run tests → build Docker image → push to ECR → deploy to EKS
- Cron job in GitHub Actions or Kubernetes CronJob for 6AM IST scraper

### 5.4 Observability Stack (Prometheus + Grafana)
Metrics to expose from the application (`/metrics` endpoint):

| Metric | Type | Description |
|---|---|---|
| `scraper_run_total` | Counter | Total scraper runs |
| `scraper_run_success_total` | Counter | Successful scraper runs |
| `scraper_run_failure_total` | Counter | Failed scraper runs |
| `scraper_jobs_fetched_total` | Gauge | Jobs fetched per source per run |
| `scraper_source_duration_seconds` | Histogram | Time per source fetch |
| `api_requests_total` | Counter | Total API requests |
| `api_response_duration_seconds` | Histogram | API response latency |
| `jobs_in_db_total` | Gauge | Total active jobs in DB |
| `jobs_expired_total` | Counter | Jobs removed due to TTL |

### 5.5 SLO Definitions (Phase 2)

| SLO | Target | Window |
|---|---|---|
| Scraper success rate | ≥ 95% of daily runs succeed | 30-day rolling |
| Page availability | ≥ 99.5% uptime | 30-day rolling |
| API p99 latency | < 500ms | Daily |
| Data freshness | Data updated by 7AM IST daily | Daily |

### 5.6 Alerting Rules (Alertmanager)
- Scraper has not run in 25 hours → PagerDuty / Slack alert
- Any source fails 3 consecutive days → warning alert
- API p99 > 1s for 5 minutes → warning alert
- Jobs in DB = 0 → critical alert

---

## 6. Acceptance Criteria Summary

| Requirement | Acceptance Test |
|---|---|
| Daily scrape at 6AM IST | Cron log shows run at 00:30 UTC |
| Page refresh does not scrape | Network tab shows no outbound API calls on refresh |
| Jobs displayed within 3s | Lighthouse performance test |
| Filters work client-side | No network request on filter change |
| Apply goes to original URL | Click Apply → verify URL is source's domain |
| Source attribution on every card | Visual inspection of every card |
| Failed source doesn't break feed | Kill one source → verify others still load |
| 7-day TTL working | Manually check DB after 8 days |

---

**Document version:** 1.0
**Status:** Approved — proceed to Tasks

# Requirements Document
## DevOps Job Portal — v1.0

---

## 1. Purpose

A personal-use, single-page job aggregation portal that collects DevOps, SRE, Platform Engineering, Application Support, Tech Support, and Cloud Engineering job listings from legally permitted sources. Serves dual purpose: active job search tool and portfolio infrastructure project.

---

## 2. Scope

### 2.1 In Scope — Phase 1
- Single page web portal, no login
- Automated daily data fetch at 6AM IST
- Job listings cached and served statically until next fetch
- Filters on the UI
- Apply link redirects to original job posting
- Source attribution on every job card
- Deploy on Netlify (frontend) + Render/Railway (backend)

### 2.2 In Scope — Phase 2
- Custom domain with public URL
- Dockerisation
- Kubernetes on AWS (EKS)
- Terraform for all infra
- Prometheus + Grafana observability stack
- SLO definitions and alerting

### 2.3 Out of Scope
- User accounts or login
- Job applications handled within the portal
- Email alerts or notifications
- Storing any user data or PII
- Any scraping beyond approved sources

---

## 3. User Profile

| Attribute | Detail |
|---|---|
| Primary user | Single user (owner) |
| Location | Chennai, India |
| Experience | 8+ years — staff/lead level |
| Target roles | DevOps, SRE, Platform, Cloud, AppSupport, TechSupport |
| Job location priority | Remote Global → Remote India → Chennai → Bengaluru → Other |

---

## 4. Data Sources & Compliance Rules

### 4.1 Source A — Open Job APIs

| # | Source | Endpoint | Fetch Frequency | Attribution Rule | Special Rules |
|---|---|---|---|---|---|
| A1 | RemoteOK | `remoteok.com/api` | Once daily, 6AM IST | Link back to RemoteOK per job card | User-Agent header mandatory |
| A2 | Remotive | `remotive.com/api/remote-jobs` | Once daily, 6AM IST | Link back to Remotive per job card | Max 4x/day; no email gating |
| A3 | Jobicy | `jobicy.com/api/v2/remote-jobs` | Once daily, 6AM IST | Attribute Jobicy as source per card | Do not redistribute to other job platforms |
| A4 | Arbeitnow | `arbeitnow.com/api/job-board-api` | Once daily, 6AM IST | Link back to Arbeitnow per card | API access can be revoked; handle gracefully |
| A5 | HN Algolia | `hn.algolia.com/api/v1/search` | Once daily, 6AM IST | Credit Hacker News as source | Search "Who's Hiring" thread only |

### 4.2 Source B — ATS Public APIs

| # | ATS | URL Pattern | Fetch Frequency | Attribution Rule |
|---|---|---|---|---|
| B1 | Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs` | Once daily, 6AM IST | Link to original job posting |
| B2 | Lever | `api.lever.co/v0/postings/{slug}` | Once daily, 6AM IST | Link to original job posting |
| B3 | Ashby | `jobs.ashbyhq.com/api/non-authenticated-open-job-listings/{slug}` | Once daily, 6AM IST | Link to original job posting |

### 4.3 Universal Compliance Rules (Non-Negotiable)

**COMP-01** — Every HTTP request from the scraper must include:
```
User-Agent: DevOpsJobsPortal/1.0 (personal project; contact: your@email.com)
```

**COMP-02** — Scraper executes exactly once per day at 6AM IST. Page visits by the user must never trigger a scrape. The scraper and the frontend are fully decoupled — a page refresh serves cached data only.

**COMP-03** — Every job card must display its source platform name as a clickable link back to the source.

**COMP-04** — The Apply button must always point to the original job URL on the source platform. No intermediation.

**COMP-05** — No job listings may be placed behind any form of email capture, signup wall, or login prompt.

**COMP-06** — Working Nomads is excluded — no confirmed free public API.

**COMP-07** — If any source API returns an error or is unreachable during the scheduled fetch, the scraper must log the failure, skip that source gracefully, and continue fetching from remaining sources. Existing cached data from that source is retained until next successful fetch.

**COMP-08** — No scraped data to be redistributed to any other job platform or third party.

---

## 5. Functional Requirements

### 5.1 Data Fetch & Storage

**FR-01** — The scraper shall run automatically at 6AM IST every day via a scheduled job (cron).

**FR-02** — The scraper shall fetch from all configured sources in a single daily run.

**FR-03** — On each successful fetch, results shall be written to a persistent data store (SQLite in Phase 1).

**FR-04** — The page shall read from the data store only. It shall never trigger a live API call on page load or page refresh.

**FR-05** — Jobs older than 7 days (based on posted date from the source where available, otherwise fetched date) shall be automatically excluded from display.

**FR-06** — Jobs that expire at 7 days shall disappear silently. No "closing soon" indicator required in Phase 1.

**FR-07** — Each job record must store:
- Job title
- Company name
- Location (raw string)
- Job type (remote / hybrid / onsite)
- Source name
- Source platform URL
- Original job apply URL
- Posted date (from source)
- Fetched date (system timestamp)
- Skills / tech stack tags
- Experience level
- Location priority tag (Remote Global / Remote India / Chennai / Bengaluru / Other)

**FR-08** — Duplicate jobs (same title + same company + same source) shall be retained as-is in Phase 1. Deduplication is not required.

### 5.2 Job Display

**FR-09** — The portal shall display all jobs within the 7-day window on a single page.

**FR-10** — Each job card shall display:
- Job Title
- Company Name
- Location
- Job Type badge
- Source (with attribution link)
- Posted Date
- Skills / Tech Stack tags
- Experience Level
- Apply button

**FR-11** — The Apply button shall open the original job posting URL in a new browser tab.

**FR-12** — Each job card shall display a location priority badge:
- 🌍 Remote Global
- 🇮🇳 Remote India
- 📍 Chennai
- 📍 Bengaluru
- 📍 Other

**FR-13** — Default sort order on page load: Remote Global first → Remote India → Chennai → Bengaluru → Other. Within each group, sorted by most recently posted.

### 5.3 Filters

**FR-14** — The following filters shall be available on the UI without page reload (client-side):

| Filter | Options |
|---|---|
| Role Type | DevOps, SRE, Platform Engineer, Application Support, Tech Support, Cloud Engineer, All |
| Location Priority | Remote Global, Remote India, Chennai, Bengaluru, Other, All |
| Job Type | Remote, Hybrid, On-site, All |
| Source | RemoteOK, Remotive, Jobicy, Arbeitnow, HN, Greenhouse, Lever, Ashby, All |
| Experience Level | Entry, Mid, Senior, Staff/Lead, All |
| Posted Within | Last 24hrs, Last 3 days, Last 7 days |

**FR-15** — Filters shall be combinable. Selecting multiple filters narrows results using AND logic.

**FR-16** — A job count indicator shall show how many jobs match the current filter selection (e.g., "42 jobs found").

**FR-17** — A "Clear all filters" button shall reset all filters to their default state.

### 5.4 Attribution & Legal Display

**FR-18** — Every job card must display the source platform name as a hyperlink to the source platform's homepage or the specific job listing on the source platform.

**FR-19** — A footer on the portal shall state that jobs are aggregated from third-party sources and that the portal does not own the listings.

---

## 6. Non-Functional Requirements

### 6.1 Performance

**NFR-01** — Page must load within 3 seconds on a standard broadband connection.

**NFR-02** — Filters must respond instantly (client-side filtering — no server round-trips).

**NFR-03** — The scraper must complete its full daily run within 30 minutes.

### 6.2 Reliability

**NFR-04** — If one or more sources fail during the daily fetch, remaining sources must still complete successfully.

**NFR-05** — Cached job data from the previous successful fetch must remain available if the scraper run fails entirely.

**NFR-06** — Scraper failures must be logged with: timestamp, source name, error type, and HTTP status code.

### 6.3 Availability

**NFR-07** — No formal SLA in Phase 1. Best-effort on free hosting tiers.

**NFR-08** — Phase 2 target: 99.5% monthly uptime, formally tracked via Prometheus + Grafana.

### 6.4 Security

**NFR-09** — No user data is collected, stored, or transmitted.

**NFR-10** — No cookies, tracking scripts, or analytics in Phase 1.

**NFR-11** — All external links (Apply, Source) must open in a new tab with `rel="noopener noreferrer"`.

### 6.5 Maintainability

**NFR-12** — Adding a new company to the Source B list must require changing only one configuration file (`companies.yaml`) — no code changes.

**NFR-13** — Adding a new Source A API must require minimal code changes — pluggable scraper module architecture.

**NFR-14** — All scraper configuration (API URLs, fetch schedule, keyword filters, User-Agent string) must be stored in environment variables or config files, not hardcoded.

### 6.6 Portability

**NFR-15** — The application must be containerisable with Docker from Day 1, even if containers are not used in Phase 1 deployment.

**NFR-16** — No dependency on any platform-specific features that would prevent migration from Netlify/Render to AWS in Phase 2.

---

## 7. Data Retention Policy

| Rule | Detail |
|---|---|
| Job TTL | 7 days from posted date (source) or fetched date (fallback) |
| Expiry behaviour | Silent removal — no user-facing indicator |
| Scrape logs | Retained 30 days (Phase 1: local file; Phase 2: centralised logging) |
| User data | None collected — nothing to retain |

---

## 8. Constraints

| Constraint | Detail |
|---|---|
| Budget | $0 in Phase 1 |
| Code authorship | Claude writes all application code |
| Infra ownership | Owner builds and maintains all infra |
| Hosting Phase 1 | Netlify (frontend) + Render or Railway (backend/scraper) |
| Hosting Phase 2 | AWS — EKS, Terraform, Prometheus + Grafana |
| Language | Python (backend/scraper), HTML/CSS/Vanilla JS (frontend) |
| Database Phase 1 | SQLite |
| Database Phase 2 | PostgreSQL (upgrade path) |

---

## 9. Assumptions

| # | Assumption |
|---|---|
| A1 | Source APIs remain publicly available and ToS does not change |
| A2 | ATS slugs for companies in the curated list are resolvable and stable |
| A3 | Daily fetch volume will not exceed rate limits of any source |
| A4 | Job data from sources includes sufficient metadata for filtering (title, location, date) |
| A5 | The portal is personal use only and will not be marketed or publicised |

---

## 10. Explicitly Out of Scope

- Email alerts or job notifications
- User accounts, profiles, or saved jobs
- Salary comparison or benchmarking
- Resume upload or application tracking
- Mobile app
- Any form of advertising or monetisation

---

**Document version:** 1.0
**Status:** Approved — proceed to PRD

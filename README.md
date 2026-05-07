# DevOps Job Portal

A personal-use, single-page job aggregation portal for DevOps, SRE,
Platform Engineering, Cloud, Application Support, and Tech Support roles.

## Status
🚧 Under active development

## What This Is
- Aggregates jobs from 8 legal sources (RemoteOK, Remotive, Jobicy,
  Arbeitnow, HN Who's Hiring, Greenhouse ATS, Lever ATS, Ashby ATS)
- Refreshes daily at 6AM IST via scheduled cron
- No login required — single page, filtered view
- Priority: Remote Global → Remote India → Chennai → Bengaluru

## Portfolio Purpose
Phase 2 will include:
- Docker + Kubernetes (AWS EKS)
- Terraform for all infra
- Prometheus + Grafana observability stack
- SLO definitions and alerting

## Docs
- [Requirements](./docs/requirements.md)
- [PRD](./docs/prd.md)
- [Tasks](./docs/tasks.md)

## Tech Stack
- Backend: Python (FastAPI)
- Frontend: HTML + CSS + Vanilla JS
- Database: SQLite (Phase 1) → PostgreSQL (Phase 2)
- Hosting Phase 1: Netlify + Render
- Hosting Phase 2: AWS EKS


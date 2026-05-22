"""
FastAPI application — read-only job portal backend.

Endpoints:
    GET /api/jobs    — all jobs within the 14-day TTL window
    GET /api/health  — last scraper run status per source

No write endpoints. No scraper trigger endpoints.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.models import HealthResponse, Job, JobsResponse
from config.settings import FRONTEND_ORIGIN
from db.database import init_db, query_health, query_jobs

app = FastAPI(
    title="InfraJobs API",
    description="Read-only API serving cached DevOps, SRE, Platform Engineering, Cloud & Infrastructure job listings.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    """Ensure the database and schema exist on first startup."""
    init_db()


@app.get("/api/jobs", response_model=JobsResponse)
def get_jobs() -> JobsResponse:
    """
    Return all job listings within the 14-day TTL window.

    Jobs are ordered by location priority (Remote Global first) then by most
    recently posted. All filtering happens client-side — this endpoint always
    returns the full cached dataset.
    """
    try:
        rows = query_jobs(ttl_days=14)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    jobs = [Job(**row) for row in rows]
    fetched_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    return JobsResponse(
        fetched_at=fetched_at,
        total=len(jobs),
        jobs=jobs,
    )


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """
    Return the most recent scraper run status and a per-source breakdown.

    Used for operational monitoring — not consumed by the frontend.
    """
    try:
        rows = query_jobs(ttl_days=14)
        total_jobs = len(rows)
        health = query_health()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return HealthResponse(
        status="ok",
        last_run=health.get("last_run"),
        last_run_status=health.get("last_run_status"),
        total_jobs=total_jobs,
        sources=health.get("sources", {}),
    )


@app.get("/")
def root() -> dict:
    """Redirect hint for the root path."""
    return {"message": "InfraJobs API. Use /api/jobs or /api/health."}

"""
FastAPI application — read-only job portal backend.

Endpoints:
    GET /          — serves frontend/index.html
    GET /api/jobs  — all jobs within the 14-day TTL window
    GET /api/health — last scraper run status per source

No write endpoints. No scraper trigger endpoints.
Static files (CSS, JS) are served via a StaticFiles mount at /.
API routes must be defined BEFORE the mount so they are not intercepted.

The daily scraper is scheduled via APScheduler at 00:30 UTC (6AM IST)
and runs inside this process — no separate cron service is required.
If the process was down at 00:30 UTC, a startup catch-up runs the scraper
once (in a background thread) when no scrape has been logged for today.
A DB-backed run lock in scraper.main prevents duplicate runs across replicas.
"""

import atexit
import os
import threading
from datetime import date, datetime, time, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.models import HealthResponse, Job, JobsResponse
from config.settings import FRONTEND_ORIGIN
from db.database import get_last_swap_at, has_run_today, init_db, query_health, query_jobs

SCRAPE_TIME_UTC = time(hour=0, minute=30)
JOBS_CACHE_MAX_AGE = 3600

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


@app.middleware("http")
async def revalidate_static_files(request: Request, call_next):
    """
    Make browsers revalidate the frontend files (HTML/CSS/JS) on every load.

    Without this, a browser can keep an old app.js after a deploy while
    loading the new index.html, which breaks the page. Revalidation is cheap:
    unchanged files return 304 via their ETag. /api/* keeps its own headers.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


def start_scheduler() -> None:
    """
    Schedule the daily scraper job using APScheduler.

    Runs run_scraper() at 00:30 UTC every day (6AM IST).
    The scheduler runs in a background thread alongside uvicorn.
    Registered with atexit so it shuts down cleanly when the process exits.
    """
    try:
        from scraper.main import run_scraper
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_scraper,
            trigger=CronTrigger(hour=SCRAPE_TIME_UTC.hour, minute=SCRAPE_TIME_UTC.minute, timezone="UTC"),
            id="daily_scraper",
            name="Daily job scraper",
            replace_existing=True,
            misfire_grace_time=6 * 3600,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
        print("[scheduler] Daily scraper scheduled at 00:30 UTC (6AM IST)")
    except Exception as e:
        print(f"[scheduler] Failed to start: {e}")


def needs_catch_up(now: datetime, ran_today: bool) -> bool:
    """
    Return True if today's scheduled scrape was missed.

    Args:
        now:       Current UTC datetime.
        ran_today: Whether scrape_logs has any entry for today's date.
    """
    return not ran_today and now.time() >= SCRAPE_TIME_UTC


def catch_up_if_missed() -> None:
    """
    Run the scraper in a background thread if today's 00:30 UTC run was missed
    (process asleep or restarting at that time). The scraper's run lock stops
    this from duplicating a run already in progress elsewhere.
    """
    now = datetime.now(tz=timezone.utc)
    if not needs_catch_up(now, has_run_today(date.today().isoformat())):
        return
    from scraper.main import run_scraper
    print("[scheduler] No scrape logged for today — running catch-up scrape")
    threading.Thread(target=run_scraper, name="catch-up-scraper", daemon=True).start()


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise the database, start the scheduler and catch up a missed run."""
    init_db()
    start_scheduler()
    try:
        catch_up_if_missed()
    except Exception as e:
        print(f"[scheduler] Catch-up check failed: {e}")


@app.get("/api/jobs", response_model=JobsResponse)
def get_jobs(request: Request, response: Response) -> JobsResponse | Response:
    """
    Return all job listings within the 14-day TTL window.

    Jobs are ordered by location priority (Remote Global first) then by most
    recently posted. All filtering happens client-side — this endpoint always
    returns the full cached dataset.

    fetched_at is the time of the last successful scrape swap (when the data
    was produced). Data changes once a day, so the response carries
    Cache-Control and an ETag keyed on that time; a matching If-None-Match
    gets a 304 with no body.
    """
    try:
        fetched_at = get_last_swap_at()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    cache_headers = {"Cache-Control": f"public, max-age={JOBS_CACHE_MAX_AGE}"}
    if fetched_at:
        # The 14-day TTL window moves daily, so include today's date too.
        cache_headers["ETag"] = f'"{fetched_at}-{date.today().isoformat()}"'
        if request.headers.get("if-none-match") == cache_headers["ETag"]:
            return Response(status_code=304, headers=cache_headers)

    try:
        rows = query_jobs(ttl_days=14)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    jobs = [Job(**row) for row in rows]
    response.headers.update(cache_headers)

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
def root() -> FileResponse:
    """Serve the InfraJobs frontend at the root URL."""
    frontend_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "frontend", "index.html"
    )
    return FileResponse(frontend_path)


# ---------------------------------------------------------------------------
# Static file serving — must be mounted AFTER all API routes so that
# /api/jobs and /api/health are not intercepted by the catch-all mount.
# ---------------------------------------------------------------------------
frontend_dir = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "frontend"
)
if os.path.exists(frontend_dir):
    app.mount(
        "/",
        StaticFiles(directory=frontend_dir, html=True),
        name="frontend",
    )

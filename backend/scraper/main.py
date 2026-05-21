"""
Scraper orchestrator — daily entry point.

Run with:
    python -m scraper.main

Triggered by cron at 06:00 IST (00:30 UTC). Must never be called from a web
request — the scraper and frontend are fully decoupled.
"""

import time
from datetime import date, datetime, timezone
from typing import Callable

from db.database import (
    count_jobs,
    delete_expired_jobs,
    delete_source_jobs_before,
    init_db,
    insert_jobs,
    purge_old_logs,
)
from scraper.logger import log_failure, log_success
from scraper.sources.ats.ashby import fetch_jobs as fetch_ashby
from scraper.sources.ats.greenhouse import fetch_jobs as fetch_greenhouse
from scraper.sources.ats.lever import fetch_jobs as fetch_lever
from scraper.sources.jobicy import fetch_jobs as fetch_jobicy
from scraper.sources.remoteok import fetch_jobs as fetch_remoteok
from scraper.sources.remotive import fetch_jobs as fetch_remotive

# Each entry: (source_name, fetch_function)
# Arbeitnow and HN Algolia removed — source files preserved as *.py.disabled
SOURCES: list[tuple[str, Callable[[], list[dict]]]] = [
    ("RemoteOK",   fetch_remoteok),
    ("Remotive",   fetch_remotive),
    ("Jobicy",     fetch_jobicy),
    ("Greenhouse", fetch_greenhouse),
    ("Lever",      fetch_lever),
    ("Ashby",      fetch_ashby),
]


def _now_utc() -> str:
    """Return current UTC time as a readable string."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def run() -> None:
    """
    Execute the full daily scrape across all configured sources.

    For each source:
    - Calls the source's fetch_jobs() function.
    - Writes returned jobs to the database in a single transaction.
    - Logs success or failure to the scrape_logs table.
    - A single source failure never stops the remaining sources.

    After all sources complete:
    - Purges scrape log entries older than LOG_RETENTION_DAYS.
    - Prints a summary line with total jobs written.
    """
    print(f"\n{'='*60}")
    print(f"  Scraper run started — {_now_utc()}")
    print(f"{'='*60}")

    init_db()

    today = date.today().isoformat()

    # --- TTL cleanup: remove jobs older than 7 days -------------------
    jobs_before = count_jobs()
    try:
        from config.settings import JOB_TTL_DAYS
    except ImportError:
        JOB_TTL_DAYS = 7

    expired = delete_expired_jobs(JOB_TTL_DAYS)
    jobs_after_ttl = count_jobs()
    print(f"\n[cleanup] Jobs before TTL cleanup : {jobs_before}")
    print(f"[cleanup] Expired jobs removed    : {expired}")
    print(f"[cleanup] Jobs after TTL cleanup  : {jobs_after_ttl}")

    # --- Per-source fetch + refresh -----------------------------------
    total_new_jobs = 0
    source_results: dict[str, int | str] = {}

    for source_name, fetch_fn in SOURCES:
        print(f"\n[{source_name}] Fetching...")
        start = time.monotonic()

        try:
            jobs = fetch_fn()
            duration = time.monotonic() - start

            # Discard jobs where role classification returned 'other' —
            # these passed the keyword filter but didn't map to a known role.
            jobs = [j for j in jobs if j.get("role_type") != "other"]

            # Replace previous days' data for this source with today's fresh batch.
            # On failure we skip this step so stale-but-valid data is preserved.
            stale_removed = delete_source_jobs_before(source_name, today)
            if stale_removed:
                print(f"[{source_name}] Removed {stale_removed} stale record(s) from previous runs.")

            if jobs:
                insert_jobs(jobs)

            log_success(source_name, len(jobs), duration)
            total_new_jobs += len(jobs)
            source_results[source_name] = len(jobs)

        except Exception as exc:
            duration = time.monotonic() - start
            http_status = None

            # Extract HTTP status code if available.
            try:
                import requests
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    http_status = exc.response.status_code
            except ImportError:
                pass

            log_failure(source_name, str(exc), http_status, duration)
            source_results[source_name] = f"FAILED: {exc}"
            # Do NOT raise — continue to next source.
            # Previous data for this source is intentionally kept intact.

    # --- Purge stale log entries --------------------------------------
    try:
        from config.settings import LOG_RETENTION_DAYS
        purge_old_logs(LOG_RETENTION_DAYS)
    except Exception as exc:
        print(f"[purge] WARNING — could not purge old logs: {exc}")

    # --- Summary ------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  Scraper run complete — {_now_utc()}")
    print(f"  New jobs written   : {total_new_jobs}")
    print(f"  Total jobs in DB   : {count_jobs()}")
    print(f"  Sources            : {len(SOURCES)}")
    for name, result in source_results.items():
        status = f"{result} jobs" if isinstance(result, int) else result
        print(f"    {name:<12} {status}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()

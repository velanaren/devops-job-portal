"""
Scraper orchestrator — daily entry point.

Run with:
    python -m scraper.main

Triggered by cron at 06:00 IST (00:30 UTC). Must never be called from a web
request — the scraper and frontend are fully decoupled.
"""

import time
from datetime import datetime, timezone
from typing import Callable

from db.database import init_db, insert_jobs, purge_old_logs
from scraper.logger import log_failure, log_success
from scraper.sources.arbeitnow import fetch_jobs as fetch_arbeitnow
from scraper.sources.ats.ashby import fetch_jobs as fetch_ashby
from scraper.sources.ats.greenhouse import fetch_jobs as fetch_greenhouse
from scraper.sources.ats.lever import fetch_jobs as fetch_lever
from scraper.sources.hn_algolia import fetch_jobs as fetch_hn
from scraper.sources.jobicy import fetch_jobs as fetch_jobicy
from scraper.sources.remoteok import fetch_jobs as fetch_remoteok
from scraper.sources.remotive import fetch_jobs as fetch_remotive

# Each entry: (source_name, fetch_function)
SOURCES: list[tuple[str, Callable[[], list[dict]]]] = [
    ("RemoteOK",   fetch_remoteok),
    ("Remotive",   fetch_remotive),
    ("Jobicy",     fetch_jobicy),
    ("Arbeitnow",  fetch_arbeitnow),
    ("HN",         fetch_hn),
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

    total_jobs = 0
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

            if jobs:
                insert_jobs(jobs)

            log_success(source_name, len(jobs), duration)
            total_jobs += len(jobs)
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

    # Purge stale log entries.
    try:
        from config.settings import LOG_RETENTION_DAYS
        purge_old_logs(LOG_RETENTION_DAYS)
    except Exception as exc:
        print(f"[purge] WARNING — could not purge old logs: {exc}")

    # Summary.
    print(f"\n{'='*60}")
    print(f"  Scraper run complete — {_now_utc()}")
    print(f"  Total jobs written : {total_jobs}")
    print(f"  Sources            : {len(SOURCES)}")
    for name, result in source_results.items():
        status = f"{result} jobs" if isinstance(result, int) else result
        print(f"    {name:<12} {status}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()

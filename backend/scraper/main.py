"""
Scraper orchestrator — daily entry point.

Run manually:
    python -m scraper.main

Triggered automatically by APScheduler inside FastAPI at 00:30 UTC (6AM IST).
Can also be triggered manually for testing.

Blue/green staging swap:
  Jobs are written to jobs_staging during the entire fetch phase.
  The live jobs table is untouched until all sources complete.
  swap_staging_to_live() atomically replaces the live table in <1ms,
  so the portal never shows 0 jobs during a scraper run.
  If the scraper crashes mid-run, staging is discarded and the portal
  continues serving the previous day's data.

Swap guard: if staging ends up far smaller than live (most sources failed),
the swap is skipped and yesterday's data is kept — see should_swap().
Run lock: a DB-backed lock prevents concurrent runs (multiple replicas, or
startup catch-up racing the cron job).
"""

import time
from collections import Counter
from datetime import date, datetime, timezone
from typing import Callable

from config.settings import MIN_SWAP_JOBS, MIN_SWAP_RATIO, SCRAPE_LOCK_TTL_HOURS
from db.database import (
    acquire_run_lock,
    clear_staging,
    clear_today_logs,
    count_jobs,
    count_staging,
    init_db,
    insert_jobs_staging,
    insert_scrape_log,
    purge_old_logs,
    reset_slug_stats_if_keywords_changed,
    release_run_lock,
    swap_staging_to_live,
)
from scraper.filters import KEYWORDS_VERSION, matched_keyword
from scraper.sources.ats.ashby import fetch_jobs as fetch_ashby
from scraper.sources.ats.greenhouse import fetch_jobs as fetch_greenhouse
from scraper.sources.ats.lever import fetch_jobs as fetch_lever
from scraper.sources.himalayas import fetch_jobs as fetch_himalayas
from scraper.sources.jobicy import fetch_jobs as fetch_jobicy
from scraper.sources.remoteok import fetch_jobs as fetch_remoteok
from scraper.sources.remotive import fetch_jobs as fetch_remotive

# Each entry: (source_name, fetch_function)
# Arbeitnow and HN Algolia removed — source files preserved as *.py.disabled
SOURCES: list[tuple[str, Callable[[], list[dict]]]] = [
    ("RemoteOK",   fetch_remoteok),
    ("Remotive",   fetch_remotive),
    ("Jobicy",     fetch_jobicy),
    ("Himalayas",  fetch_himalayas),
    ("Greenhouse", fetch_greenhouse),
    ("Lever",      fetch_lever),
    ("Ashby",      fetch_ashby),
]


def _now_utc() -> str:
    """Return current UTC time as a readable string."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def should_swap(staging_count: int, live_count: int) -> bool:
    """
    Decide whether staging is healthy enough to replace the live table.

    Guards against a run where most sources failed overwriting yesterday's
    good data with a near-empty table.

    Args:
        staging_count: Jobs in jobs_staging after all sources ran.
        live_count:    Jobs currently in the live jobs table.

    Returns:
        True if staging has at least MIN_SWAP_JOBS jobs and at least
        MIN_SWAP_RATIO × live_count jobs. An empty live table always swaps
        when staging is non-empty (first run / recovery).
    """
    if staging_count == 0:
        return False
    if live_count == 0:
        return True
    return staging_count >= MIN_SWAP_JOBS and staging_count >= MIN_SWAP_RATIO * live_count


def run_scraper() -> None:
    """
    Execute the full daily scrape across all configured sources.

    Writes all fetched jobs to jobs_staging during the fetch phase,
    leaving the live jobs table (and the portal) untouched.
    After all sources complete, swap_staging_to_live() atomically
    promotes staging to live in a single exclusive SQLite transaction.
    scrape_logs are written only after a successful swap.

    For each source:
    - Calls the source's fetch_jobs() function.
    - Writes returned jobs to the staging table.
    - Logs success or failure to pending_logs (in memory).
    - A single source failure never stops the remaining sources.
      Failed sources contribute 0 staging jobs — the live table is safe.

    After all sources complete:
    - Swaps staging to live atomically.
    - Writes all collected log entries to scrape_logs.
    - Purges scrape log entries older than LOG_RETENTION_DAYS.

    Called by APScheduler at 00:30 UTC daily, or directly via
    `python -m scraper.main` for manual runs.
    """
    print(f"\n{'='*60}")
    print(f"  Scraper run started — {_now_utc()}")
    print(f"{'='*60}")

    init_db()

    if not acquire_run_lock(SCRAPE_LOCK_TTL_HOURS):
        print("[lock] Another scraper run is in progress — skipping this run")
        return
    try:
        _run_locked()
    finally:
        release_run_lock()


def _run_locked() -> None:
    """Body of run_scraper(), executed while holding the run lock."""
    today = date.today().isoformat()

    if reset_slug_stats_if_keywords_changed(KEYWORDS_VERSION):
        print(f"[slugs] Keyword rules changed ({KEYWORDS_VERSION}) — all ATS companies re-checked this run")

    # --- Clear staging: live table stays untouched throughout ---------
    clear_staging()
    print(f"[staging] Staging table cleared — fetching fresh data")

    # --- Per-source fetch into staging --------------------------------
    total_staging_jobs = 0
    pending_logs: list[dict] = []
    keyword_counts: Counter = Counter()

    for source_name, fetch_fn in SOURCES:
        start = time.monotonic()

        try:
            jobs = fetch_fn()
            duration = time.monotonic() - start

            # Discard jobs where role classification returned 'other'.
            jobs = [j for j in jobs if j.get("role_type") != "other"]

            # Discard Global-tagged jobs — these are non-India, non-remote-global
            # locations (US/EU/etc.) that are not relevant to this portal.
            before_filter = len(jobs)
            jobs = [j for j in jobs if j.get("location_tag") != "Global"]
            filtered_count = before_filter - len(jobs)
            if filtered_count > 0:
                print(f"  [{source_name}] {filtered_count} Global jobs excluded")

            keyword_counts.update(matched_keyword(j.get("title", "")) or "?" for j in jobs)
            inserted = insert_jobs_staging(jobs) if jobs else 0
            duplicates = len(jobs) - inserted

            total_staging_jobs += inserted
            print(
                f"[{source_name:<12}] SUCCESS — {inserted} jobs "
                f"({duplicates} cross-source duplicates skipped, {duration:.1f}s)"
            )
            pending_logs.append({
                "run_date": today,
                "source_name": source_name,
                "status": "success",
                "jobs_fetched": inserted,
                "error_message": None,
                "http_status": None,
                "duration_seconds": round(duration, 2),
            })

        except Exception as exc:
            duration = time.monotonic() - start
            http_status = None

            try:
                import requests
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    http_status = exc.response.status_code
            except ImportError:
                pass

            print(f"[{source_name:<12}] FAILURE — {exc}")
            pending_logs.append({
                "run_date": today,
                "source_name": source_name,
                "status": "failure",
                "jobs_fetched": 0,
                "error_message": str(exc),
                "http_status": http_status,
                "duration_seconds": round(duration, 2),
            })
            # Do NOT raise — continue to next source.
            # Staging has partial data — live table remains safe.

    # --- Atomic swap: staging → live ----------------------------------
    print(f"\n{'='*60}")
    print("[keywords] Top matched title keywords this run:")
    for keyword, count in keyword_counts.most_common(15):
        print(f"  {count:>5}  {keyword}")
    staging_count = count_staging()
    current_live = count_jobs()
    if should_swap(staging_count, current_live):
        print("[staging] All sources complete — swapping to live")
        live_count = swap_staging_to_live()
        print(f"[staging] Live portal now has {live_count} jobs")
    else:
        print(
            f"[staging] SWAP SKIPPED — staging has {staging_count} jobs vs "
            f"{current_live} live (min {MIN_SWAP_JOBS}, ratio {MIN_SWAP_RATIO}). "
            "Keeping previous data."
        )
        clear_staging()

    # --- Write scrape logs (also when the swap was skipped, so the
    # startup catch-up does not re-run the scraper repeatedly) ---------
    clear_today_logs(today)
    for log in pending_logs:
        insert_scrape_log(log)

    # --- Purge stale log entries --------------------------------------
    try:
        from config.settings import LOG_RETENTION_DAYS
        purge_old_logs(LOG_RETENTION_DAYS)
    except Exception as exc:
        print(f"[purge] WARNING — could not purge old logs: {exc}")

    # --- Summary ------------------------------------------------------
    print(f"  Scraper run complete — {_now_utc()}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_scraper()

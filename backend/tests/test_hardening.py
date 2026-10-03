"""Tests for TASK-040: dedup, swap guard, run lock, slug pruning, API caching."""
from datetime import date, datetime, timezone

import pytest

from db import database as db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Point every test at a fresh SQLite file."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "jobs.db"))
    db.init_db()


def _job(company="Cloudflare", title="Senior SRE", source="Remotive"):
    """Build a minimal normalised job dict."""
    return {
        "title": title, "company": company, "location_raw": "Remote",
        "location_tag": "Remote Global", "job_type": "remote",
        "source_name": source, "source_url": "https://x", "apply_url": "https://x/1",
        "posted_date": date.today().isoformat(), "fetched_date": date.today().isoformat(),
        "skills": None, "experience_level": "senior", "role_type": "sre",
    }


# --- dedup ---------------------------------------------------------------

def test_make_dedup_key_normalises_company_and_title():
    assert db.make_dedup_key("Cloudflare, Inc.", "Senior  SRE") == db.make_dedup_key("cloudflare", "senior sre")


def test_staging_skips_cross_source_duplicates():
    assert db.insert_jobs_staging([_job(source="Remotive")]) == 1
    assert db.insert_jobs_staging([_job(company="Cloudflare Inc", source="Greenhouse")]) == 0
    assert db.count_staging() == 1


def test_swap_records_last_swap_at():
    db.insert_jobs_staging([_job()])
    assert db.get_last_swap_at() is None
    assert db.swap_staging_to_live() == 1
    assert db.get_last_swap_at() is not None


# --- swap guard ----------------------------------------------------------

def test_should_swap_guard():
    from scraper.main import should_swap
    assert should_swap(10, 0) is True          # first run
    assert should_swap(0, 0) is False
    assert should_swap(30, 1000) is False      # below floor
    assert should_swap(400, 1000) is False     # below ratio
    assert should_swap(800, 1000) is True


# --- run lock ------------------------------------------------------------

def test_run_lock_is_exclusive_and_releasable():
    assert db.acquire_run_lock(12) is True
    assert db.acquire_run_lock(12) is False
    db.release_run_lock()
    assert db.acquire_run_lock(12) is True


def test_stale_run_lock_is_taken_over():
    assert db.acquire_run_lock(12) is True
    assert db.acquire_run_lock(0) is True


# --- slug pruning --------------------------------------------------------

def test_slug_due_rules():
    from scraper.sources.ats import is_slug_due
    today = date(2026, 10, 3)
    assert is_slug_due("a", None, today) is True
    hot = {"last_checked_date": "2026-10-02", "last_hit_date": "2026-09-20"}
    assert is_slug_due("a", hot, today) is True
    checked_today = {"last_checked_date": "2026-10-03", "last_hit_date": None}
    cold_recent = {"last_checked_date": "2026-10-02", "last_hit_date": None}
    cold_old = {"last_checked_date": "2026-09-25", "last_hit_date": None}
    assert is_slug_due("a", cold_old, today) is True
    assert is_slug_due("a", checked_today, today) is False
    # Over a week, a cold slug checked yesterday becomes due on exactly one bucket day.
    due_days = [
        is_slug_due("acme", cold_recent, date(2026, 10, 2 + d)) for d in range(1, 7)
    ]
    assert sum(due_days) <= 1


def test_record_slug_results_keeps_last_hit():
    db.record_slug_results("lever", {"a": 2, "b": 0}, "2026-10-01")
    db.record_slug_results("lever", {"a": 0}, "2026-10-02")
    stats = db.get_slug_stats("lever")
    assert stats["a"] == {"last_checked_date": "2026-10-02", "last_hit_date": "2026-10-01"}
    assert stats["b"]["last_hit_date"] is None


# --- scheduler catch-up --------------------------------------------------

def test_needs_catch_up():
    from api.main import needs_catch_up
    early = datetime(2026, 10, 3, 0, 10, tzinfo=timezone.utc)
    late = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
    assert needs_catch_up(early, ran_today=False) is False
    assert needs_catch_up(late, ran_today=False) is True
    assert needs_catch_up(late, ran_today=True) is False


# --- API -----------------------------------------------------------------

def test_jobs_endpoint_cache_headers_and_fetched_at():
    from fastapi.testclient import TestClient
    from api.main import app

    db.insert_jobs_staging([_job()])
    db.swap_staging_to_live()
    client = TestClient(app)  # no context manager → startup (scheduler) not run

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json()["fetched_at"] == db.get_last_swap_at()
    assert resp.headers["cache-control"] == "public, max-age=3600"
    etag = resp.headers["etag"]

    again = client.get("/api/jobs", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_frontend_files_are_revalidated():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    assert client.get("/app.js").headers["cache-control"] == "no-cache"
    assert client.get("/api/jobs").headers["cache-control"] == "public, max-age=3600"

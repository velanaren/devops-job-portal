import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def _get_db_path() -> str:
    """Return DB path from environment variable, defaulting to ./data/jobs.db."""
    return os.environ.get("DB_PATH", "./data/jobs.db")


def get_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection with row_factory set to Row.

    The database file and its parent directory are created if they do not exist.
    """
    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Initialise the database by executing schema.sql.

    Safe to call multiple times — all statements use CREATE TABLE IF NOT EXISTS.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    with get_connection() as conn:
        conn.executescript(schema_path.read_text())
        # Migrate databases created before dedup_key existed.
        for table in ("jobs", "jobs_staging"):
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "dedup_key" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN dedup_key TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_dedup "
            "ON jobs_staging(dedup_key)"
        )


_COMPANY_SUFFIX_RE = re.compile(
    r"\b(inc|llc|ltd|limited|corp|corporation|co|gmbh|plc|pvt|private|technologies|labs|hq)\b"
)


def make_dedup_key(company: str, title: str) -> str:
    """
    Build a cross-source dedup key from normalised company name and title.

    Lower-cases, strips punctuation and common legal suffixes so that e.g.
    "Cloudflare, Inc." / "cloudflare" and "Senior SRE" / "Senior SRE " collide.

    Args:
        company: Company name as reported by the source.
        title:   Job title.

    Returns:
        String key of the form "<company>|<title>".
    """
    def _norm(text: str) -> str:
        text = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    company_norm = _norm(_COMPANY_SUFFIX_RE.sub(" ", _norm(company))).replace(" ", "")
    return f"{company_norm}|{_norm(title)}"


def insert_job(job: dict) -> None:
    """
    Insert a single normalised job record into the jobs table.

    Args:
        job: Dict with keys matching the jobs table columns (excluding id and created_at).
    """
    sql = """
        INSERT INTO jobs (
            title, company, location_raw, location_tag, job_type,
            source_name, source_url, apply_url,
            posted_date, fetched_date, skills, experience_level, role_type
        ) VALUES (
            :title, :company, :location_raw, :location_tag, :job_type,
            :source_name, :source_url, :apply_url,
            :posted_date, :fetched_date, :skills, :experience_level, :role_type
        )
    """
    with get_connection() as conn:
        conn.execute(sql, job)


def insert_jobs(jobs: list[dict]) -> None:
    """
    Insert multiple normalised job records in a single transaction.

    Args:
        jobs: List of dicts, each matching the jobs table columns.
    """
    sql = """
        INSERT INTO jobs (
            title, company, location_raw, location_tag, job_type,
            source_name, source_url, apply_url,
            posted_date, fetched_date, skills, experience_level, role_type
        ) VALUES (
            :title, :company, :location_raw, :location_tag, :job_type,
            :source_name, :source_url, :apply_url,
            :posted_date, :fetched_date, :skills, :experience_level, :role_type
        )
    """
    with get_connection() as conn:
        conn.executemany(sql, jobs)


def insert_scrape_log(log: dict) -> None:
    """
    Insert a scrape run log entry into the scrape_logs table.

    Args:
        log: Dict with keys: run_date, source_name, status, jobs_fetched,
             error_message, http_status, duration_seconds.
    """
    sql = """
        INSERT INTO scrape_logs (
            run_date, source_name, status, jobs_fetched,
            error_message, http_status, duration_seconds
        ) VALUES (
            :run_date, :source_name, :status, :jobs_fetched,
            :error_message, :http_status, :duration_seconds
        )
    """
    with get_connection() as conn:
        conn.execute(sql, log)


def query_jobs(ttl_days: int = 14) -> list[dict]:
    """
    Return all jobs within the TTL window, ordered by location priority then posted date.

    Args:
        ttl_days: Jobs older than this many days are excluded (default 14).

    Returns:
        List of job dicts ordered by location priority (Remote Global first) then
        most recently posted.
    """
    cutoff = (date.today() - timedelta(days=ttl_days)).isoformat()

    location_priority = """
        CASE location_tag
            WHEN 'Remote Global' THEN 1
            WHEN 'Remote India'  THEN 2
            WHEN 'Bengaluru'     THEN 3
            WHEN 'Chennai'       THEN 4
            WHEN 'Hyderabad'     THEN 5
            WHEN 'Pune'          THEN 6
            WHEN 'Mumbai'        THEN 7
            WHEN 'Delhi NCR'     THEN 8
            WHEN 'Other India'   THEN 9
            ELSE                      10
        END
    """

    sql = f"""
        SELECT *
        FROM jobs
        WHERE COALESCE(posted_date, fetched_date) >= :cutoff
        ORDER BY {location_priority}, COALESCE(posted_date, fetched_date) DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, {"cutoff": cutoff}).fetchall()
    return [dict(row) for row in rows]


def query_health() -> dict:
    """
    Return scraper health summary: last run timestamp and per-source status.

    Returns:
        Dict with keys: last_run, last_run_status, sources (dict of source → status).
    """
    sql_last_run = """
        SELECT run_date, status
        FROM scrape_logs
        ORDER BY created_at DESC
        LIMIT 1
    """
    sql_sources = """
        SELECT source_name, status
        FROM scrape_logs
        WHERE run_date = (SELECT MAX(run_date) FROM scrape_logs)
    """
    with get_connection() as conn:
        last = conn.execute(sql_last_run).fetchone()
        source_rows = conn.execute(sql_sources).fetchall()

    sources = {row["source_name"]: row["status"] for row in source_rows}

    return {
        "last_run": last["run_date"] if last else None,
        "last_run_status": last["status"] if last else None,
        "sources": sources,
    }


def count_jobs() -> int:
    """
    Return the total number of job records currently in the jobs table.

    Returns:
        Integer row count.
    """
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
    return row[0]


def clear_staging() -> None:
    """Clear the staging table before a new scraper run."""
    with get_connection() as conn:
        conn.execute("DELETE FROM jobs_staging")


def insert_jobs_staging(jobs: list[dict]) -> int:
    """
    Insert jobs into staging table (not live jobs table), skipping duplicates.

    A UNIQUE index on dedup_key (normalised company + title) means the same
    job seen from several sources is stored once — the first source wins.

    Args:
        jobs: List of normalised job dicts.

    Returns:
        Number of rows actually inserted (duplicates excluded).
    """
    sql = """
        INSERT OR IGNORE INTO jobs_staging (
            title, company, location_raw, location_tag,
            job_type, source_name, source_url, apply_url,
            posted_date, fetched_date, skills,
            experience_level, role_type, dedup_key
        ) VALUES (
            :title, :company, :location_raw, :location_tag,
            :job_type, :source_name, :source_url, :apply_url,
            :posted_date, :fetched_date, :skills,
            :experience_level, :role_type, :dedup_key
        )
    """
    rows = [
        {**job, "dedup_key": make_dedup_key(job.get("company", ""), job.get("title", ""))}
        for job in jobs
    ]
    with get_connection() as conn:
        before = conn.total_changes
        conn.executemany(sql, rows)
        return conn.total_changes - before


def count_staging() -> int:
    """Return the number of rows currently in jobs_staging."""
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs_staging").fetchone()[0]


def swap_staging_to_live() -> int:
    """
    Atomically swap staging table to live jobs table.

    Uses an EXCLUSIVE transaction so no reader sees a partial state.
    The portal is job-free for only the duration of this single transaction
    (typically <1ms), not for the entire scraper run.

    If this function raises, the live table is untouched — the portal
    continues to serve the previous day's data.

    Returns:
        Number of jobs now in the live jobs table.
    """
    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None → autocommit mode so we can issue BEGIN EXCLUSIVE.
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("DELETE FROM jobs")
        conn.execute(
            "INSERT INTO jobs (title, company, location_raw, location_tag, "
            "job_type, source_name, source_url, apply_url, posted_date, "
            "fetched_date, skills, experience_level, role_type, dedup_key, created_at) "
            "SELECT title, company, location_raw, location_tag, "
            "job_type, source_name, source_url, apply_url, posted_date, "
            "fetched_date, skills, experience_level, role_type, dedup_key, created_at "
            "FROM jobs_staging"
        )
        conn.execute("DELETE FROM jobs_staging")
        conn.execute(
            "INSERT OR REPLACE INTO scrape_meta (key, value) VALUES ('last_swap_at', :ts)",
            {"ts": _utc_now_str()},
        )
        row = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
        conn.execute("COMMIT")
        return row[0]
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def clear_jobs() -> int:
    """
    Delete all rows from the jobs table.

    Called at the start of each scraper run to ensure a clean slate — every
    run produces a fresh, duplicate-free dataset.

    Returns:
        Number of rows deleted.
    """
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM jobs")
        return cursor.rowcount


def clear_today_logs(today: str) -> int:
    """
    Delete all scrape_logs entries for today's date.

    Called at the start of each scraper run so that if the scraper is re-run
    on the same day, the log table does not accumulate duplicate run rows.

    Args:
        today: ISO date string (YYYY-MM-DD) for the current run date.

    Returns:
        Number of rows deleted.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM scrape_logs WHERE run_date = :today", {"today": today}
        )
        return cursor.rowcount


def purge_old_logs(retention_days: int = 30) -> None:
    """
    Delete scrape log entries older than retention_days.

    Args:
        retention_days: Logs older than this many days are deleted (default 30).
    """
    cutoff = (date.today() - timedelta(days=retention_days)).isoformat()
    with get_connection() as conn:
        conn.execute("DELETE FROM scrape_logs WHERE run_date < :cutoff", {"cutoff": cutoff})


# ---------------------------------------------------------------------------
# Scrape metadata — last swap time and the cross-process run lock
# ---------------------------------------------------------------------------

def _utc_now_str() -> str:
    """Return the current UTC time as 'YYYY-MM-DDTHH:MM:SS'."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def get_last_swap_at() -> str | None:
    """
    Return the UTC timestamp of the last successful staging→live swap.

    This is when the live data was actually produced, and is what the
    frontend shows as "Last updated". None if no swap has happened yet.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM scrape_meta WHERE key = 'last_swap_at'"
        ).fetchone()
    return row["value"] if row else None


def has_run_today(today: str) -> bool:
    """
    Return True if any scrape_logs entry exists for the given run date.

    Args:
        today: ISO date string (YYYY-MM-DD).
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM scrape_logs WHERE run_date = :today LIMIT 1", {"today": today}
        ).fetchone()
    return row is not None


def acquire_run_lock(ttl_hours: float) -> bool:
    """
    Try to take the scraper run lock stored in scrape_meta.

    Prevents duplicate concurrent scrapes when several API replicas (or a
    startup catch-up and the cron job) fire at once. A lock older than
    ttl_hours is treated as stale (crashed run) and taken over.

    Args:
        ttl_hours: Age after which an existing lock is considered stale.

    Returns:
        True if the lock was acquired, False if another run holds it.
    """
    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT value FROM scrape_meta WHERE key = 'run_lock'").fetchone()
        now = datetime.now(tz=timezone.utc)
        if row and row[0]:
            held_since = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            if now - held_since < timedelta(hours=ttl_hours):
                conn.execute("ROLLBACK")
                return False
        conn.execute(
            "INSERT OR REPLACE INTO scrape_meta (key, value) VALUES ('run_lock', :ts)",
            {"ts": now.strftime("%Y-%m-%dT%H:%M:%S")},
        )
        conn.execute("COMMIT")
        return True
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def release_run_lock() -> None:
    """Release the scraper run lock."""
    with get_connection() as conn:
        conn.execute("DELETE FROM scrape_meta WHERE key = 'run_lock'")


# ---------------------------------------------------------------------------
# ATS slug stats — hot/cold pruning
# ---------------------------------------------------------------------------

def get_slug_stats(ats: str) -> dict[str, dict]:
    """
    Return polling history for every known slug of one ATS.

    Args:
        ats: 'greenhouse', 'lever' or 'ashby'.

    Returns:
        Dict slug → {"last_checked_date": str|None, "last_hit_date": str|None}.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT slug, last_checked_date, last_hit_date FROM slug_stats WHERE ats = :ats",
            {"ats": ats},
        ).fetchall()
    return {
        row["slug"]: {
            "last_checked_date": row["last_checked_date"],
            "last_hit_date": row["last_hit_date"],
        }
        for row in rows
    }


def record_slug_results(ats: str, results: dict[str, int], today: str) -> None:
    """
    Record which slugs were checked today and which returned matching jobs.

    Args:
        ats:     ATS identifier.
        results: slug → number of matching jobs returned. Slugs whose fetch
                 errored should be omitted so they are retried next run.
        today:   ISO date string.
    """
    sql = """
        INSERT INTO slug_stats (ats, slug, last_checked_date, last_hit_date)
        VALUES (:ats, :slug, :today, :hit)
        ON CONFLICT(ats, slug) DO UPDATE SET
            last_checked_date = excluded.last_checked_date,
            last_hit_date = COALESCE(excluded.last_hit_date, slug_stats.last_hit_date)
    """
    params = [
        {"ats": ats, "slug": slug, "today": today, "hit": today if hits > 0 else None}
        for slug, hits in results.items()
    ]
    with get_connection() as conn:
        conn.executemany(sql, params)


def reset_slug_stats_if_keywords_changed(keywords_version: str) -> bool:
    """
    Clear ATS slug history once whenever the keyword rules change.

    Slug pruning polls "cold" companies (no matching job in SLUG_HOT_DAYS)
    only weekly. After a keyword change, companies that never matched the
    old rules may now have matching jobs, so every slug is re-checked daily
    until its hot/cold state is re-learned under the new rules.

    Args:
        keywords_version: scraper.filters.KEYWORDS_VERSION.

    Returns:
        True if the history was reset on this call.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM scrape_meta WHERE key = 'keywords_version'"
        ).fetchone()
        if row and row["value"] == keywords_version:
            return False
        conn.execute("DELETE FROM slug_stats")
        conn.execute(
            "INSERT OR REPLACE INTO scrape_meta (key, value) VALUES ('keywords_version', :v)",
            {"v": keywords_version},
        )
    return True

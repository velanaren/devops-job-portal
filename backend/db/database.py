import os
import sqlite3
from datetime import date, timedelta
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


def insert_jobs_staging(jobs: list[dict]) -> None:
    """Insert jobs into staging table (not live jobs table)."""
    sql = """
        INSERT INTO jobs_staging (
            title, company, location_raw, location_tag,
            job_type, source_name, source_url, apply_url,
            posted_date, fetched_date, skills,
            experience_level, role_type
        ) VALUES (
            :title, :company, :location_raw, :location_tag,
            :job_type, :source_name, :source_url, :apply_url,
            :posted_date, :fetched_date, :skills,
            :experience_level, :role_type
        )
    """
    with get_connection() as conn:
        conn.executemany(sql, jobs)


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
            "fetched_date, skills, experience_level, role_type, created_at) "
            "SELECT title, company, location_raw, location_tag, "
            "job_type, source_name, source_url, apply_url, posted_date, "
            "fetched_date, skills, experience_level, role_type, created_at "
            "FROM jobs_staging"
        )
        conn.execute("DELETE FROM jobs_staging")
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

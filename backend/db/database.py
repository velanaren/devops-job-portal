import os
import sqlite3
from datetime import date, datetime, timedelta
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


def query_jobs(ttl_days: int = 7) -> list[dict]:
    """
    Return all jobs within the TTL window, ordered by location priority then posted date.

    Args:
        ttl_days: Jobs older than this many days are excluded (default 7).

    Returns:
        List of job dicts ordered by location priority (Remote Global first) then
        most recently posted.
    """
    cutoff = (date.today() - timedelta(days=ttl_days)).isoformat()

    location_priority = """
        CASE location_tag
            WHEN 'Remote Global' THEN 1
            WHEN 'Remote India'  THEN 2
            WHEN 'Chennai'       THEN 3
            WHEN 'Bengaluru'     THEN 4
            ELSE                      5
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


def purge_old_logs(retention_days: int = 30) -> None:
    """
    Delete scrape log entries older than retention_days.

    Args:
        retention_days: Logs older than this many days are deleted (default 30).
    """
    cutoff = (date.today() - timedelta(days=retention_days)).isoformat()
    with get_connection() as conn:
        conn.execute("DELETE FROM scrape_logs WHERE run_date < :cutoff", {"cutoff": cutoff})

from datetime import date

from db.database import insert_scrape_log


def log_success(source_name: str, jobs_fetched: int, duration_seconds: float = 0.0) -> None:
    """
    Record a successful scrape run for a source and print a summary line.

    Args:
        source_name:      Human-readable source identifier (e.g. 'RemoteOK').
        jobs_fetched:     Number of jobs returned by this source.
        duration_seconds: Wall-clock seconds the fetch took.
    """
    insert_scrape_log({
        "run_date": date.today().isoformat(),
        "source_name": source_name,
        "status": "success",
        "jobs_fetched": jobs_fetched,
        "error_message": None,
        "http_status": None,
        "duration_seconds": round(duration_seconds, 2),
    })
    print(f"[{source_name}] SUCCESS — {jobs_fetched} jobs ({duration_seconds:.1f}s)")


def log_failure(
    source_name: str,
    error_message: str,
    http_status: int | None = None,
    duration_seconds: float = 0.0,
) -> None:
    """
    Record a failed scrape run for a source and print an error line.

    Args:
        source_name:      Human-readable source identifier.
        error_message:    Exception message or description of what went wrong.
        http_status:      HTTP status code if the failure was an HTTP error.
        duration_seconds: Wall-clock seconds elapsed before failure.
    """
    insert_scrape_log({
        "run_date": date.today().isoformat(),
        "source_name": source_name,
        "status": "failure",
        "jobs_fetched": 0,
        "error_message": error_message,
        "http_status": http_status,
        "duration_seconds": round(duration_seconds, 2),
    })
    print(f"[{source_name}] FAILURE — {error_message}")

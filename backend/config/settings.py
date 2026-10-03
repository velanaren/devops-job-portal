import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Application ---
USER_AGENT: str = os.environ.get(
    "USER_AGENT",
    "InfraJobs/1.0 (personal project; contact: svelayuthamnaren@gmail.com)",
)
DB_PATH: str = os.environ.get("DB_PATH", "./data/jobs.db")
LOG_RETENTION_DAYS: int = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
JOB_TTL_DAYS: int = int(os.environ.get("JOB_TTL_DAYS", "14"))

# --- API ---
API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("API_PORT", "8000"))
FRONTEND_ORIGIN: str = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

# --- Scraper ---
SCRAPE_SCHEDULE: str = os.environ.get("SCRAPE_SCHEDULE", "0 1 * * *")
# Skip the staging→live swap (keep yesterday's data) when staging has fewer
# than MIN_SWAP_JOBS jobs or less than MIN_SWAP_RATIO × the current live count.
MIN_SWAP_JOBS: int = int(os.environ.get("MIN_SWAP_JOBS", "50"))
MIN_SWAP_RATIO: float = float(os.environ.get("MIN_SWAP_RATIO", "0.5"))
# A run lock older than this is treated as stale (crashed run).
SCRAPE_LOCK_TTL_HOURS: float = float(os.environ.get("SCRAPE_LOCK_TTL_HOURS", "12"))
# ATS slug pruning: slugs with a matching job in the last SLUG_HOT_DAYS are
# polled daily; all other slugs once every SLUG_COLD_INTERVAL_DAYS.
SLUG_HOT_DAYS: int = int(os.environ.get("SLUG_HOT_DAYS", "30"))
SLUG_COLD_INTERVAL_DAYS: int = int(os.environ.get("SLUG_COLD_INTERVAL_DAYS", "7"))

# --- Derived ---
COMPANIES_YAML_PATH: Path = Path(__file__).parent / "companies.yaml"

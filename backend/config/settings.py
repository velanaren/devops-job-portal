import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Application ---
USER_AGENT: str = os.environ.get(
    "USER_AGENT",
    "DevOpsJobsPortal/1.0 (personal project; contact: your@email.com)",
)
DB_PATH: str = os.environ.get("DB_PATH", "./data/jobs.db")
LOG_RETENTION_DAYS: int = int(os.environ.get("LOG_RETENTION_DAYS", "30"))

# --- API ---
API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("API_PORT", "8000"))
FRONTEND_ORIGIN: str = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

# --- Scraper ---
SCRAPE_SCHEDULE: str = os.environ.get("SCRAPE_SCHEDULE", "0 1 * * *")

# --- Derived ---
COMPANIES_YAML_PATH: Path = Path(__file__).parent / "companies.yaml"

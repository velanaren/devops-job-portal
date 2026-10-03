import re
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Callable

import yaml

from config.settings import COMPANIES_YAML_PATH, SLUG_COLD_INTERVAL_DAYS, SLUG_HOT_DAYS
from db.database import get_slug_stats, record_slug_results

_SLUGS_DIR = Path(__file__).parent.parent.parent.parent / "config" / "slugs"


def load_companies(ats: str) -> list[dict]:
    """
    Return companies for the given ATS.

    Source of truth: backend/config/slugs/{ats}_slugs.txt (one slug per line),
    committed to git. companies.yaml is only a fallback used when the slug
    file for that ATS is absent (e.g. a minimal local setup).

    Args:
        ats: ATS identifier — 'greenhouse', 'lever', or 'ashby'.

    Returns:
        List of dicts with keys: name, ats, slug.
        When loaded from the slug file, name == slug (display name unknown).
    """
    slug_file = _SLUGS_DIR / f"{ats}_slugs.txt"

    if slug_file.exists():
        slugs = [line.strip() for line in slug_file.read_text().splitlines() if line.strip()]
        return [{"name": s, "ats": ats, "slug": s} for s in slugs]

    # Fallback — curated companies.yaml list.
    with open(COMPANIES_YAML_PATH) as f:
        data = yaml.safe_load(f)
    return [c for c in data.get("companies", []) if c.get("ats") == ats]


def strip_html(html: str) -> str:
    """Remove HTML tags from a string, returning plain text."""
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def is_slug_due(slug: str, stats: dict | None, today: date) -> bool:
    """
    Decide whether an ATS slug should be polled today.

    - Never checked → due (bootstraps a full run the first time).
    - Hot (matching job within SLUG_HOT_DAYS) → due daily.
    - Cold → due on its stable weekday bucket (crc32(slug) % 7), so cold
      slugs are spread evenly across the week, or whenever it has not been
      checked for SLUG_COLD_INTERVAL_DAYS (safety net).

    Args:
        slug:  Company slug.
        stats: Row from get_slug_stats() or None.
        today: Current date.

    Returns:
        True if the slug should be fetched in this run.
    """
    if not stats or not stats.get("last_checked_date"):
        return True
    last_hit = stats.get("last_hit_date")
    if last_hit and (today - date.fromisoformat(last_hit)).days <= SLUG_HOT_DAYS:
        return True
    days_since_check = (today - date.fromisoformat(stats["last_checked_date"])).days
    if days_since_check >= SLUG_COLD_INTERVAL_DAYS:
        return True
    return days_since_check >= 1 and zlib.crc32(slug.encode()) % 7 == today.weekday()


def fetch_ats_companies(
    ats: str,
    fetch_one: Callable[[dict, str], list[dict]],
    max_workers: int,
) -> list[dict]:
    """
    Fetch jobs for every due company of one ATS and record slug stats.

    Args:
        ats:         ATS identifier.
        fetch_one:   Function(company, today_iso) → list of normalised jobs.
        max_workers: Thread pool size.

    Returns:
        Combined list of normalised jobs.
    """
    today = date.today()
    today_iso = today.isoformat()
    companies = load_companies(ats)
    stats = get_slug_stats(ats)
    due = [c for c in companies if is_slug_due(c["slug"], stats.get(c["slug"]), today)]
    print(f"  [{ats}] polling {len(due)}/{len(companies)} slugs (hot + due cold)")

    jobs: list[dict] = []
    results: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_one, c, today_iso): c for c in due}
        for future in as_completed(futures):
            try:
                company_jobs = future.result()
            except Exception:
                continue  # errored slugs stay unrecorded so they retry next run
            jobs.extend(company_jobs)
            results[futures[future]["slug"]] = len(company_jobs)

    record_slug_results(ats, results, today_iso)
    return jobs

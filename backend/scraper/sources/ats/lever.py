import time
from datetime import date, datetime, timezone

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.sources.ats import load_companies, strip_html
from scraper.tagger import tag_location

SOURCE_NAME = "Lever"
API_BASE = "https://api.lever.co/v0/postings"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def _fetch_company_jobs(slug: str) -> list[dict]:
    """
    Fetch all open job postings for a single Lever company slug.

    Args:
        slug: Lever posting identifier (e.g. 'grafanalabs').

    Returns:
        Raw list of posting dicts from the Lever API.
    """
    url = f"{API_BASE}/{slug}"
    response = requests.get(
        url,
        headers=HEADERS,
        params={"mode": "json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    # Lever returns either a list directly or {"data": [...]}
    return data if isinstance(data, list) else data.get("data", [])


def _epoch_ms_to_date(epoch_ms: int | None, fallback: str) -> str:
    """Convert a Lever epoch-millisecond timestamp to an ISO date string."""
    if not epoch_ms:
        return fallback
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).date().isoformat()
    except (OSError, ValueError, OverflowError):
        return fallback


def _extract_skills(item: dict) -> str:
    """Pull skill keywords from Lever posting lists (requirements, etc.)."""
    lists = item.get("lists") or []
    parts: list[str] = []
    for lst in lists:
        content = strip_html(lst.get("content") or "")
        if content:
            parts.append(content[:200])
    return "; ".join(parts)[:500] if parts else ""


def _normalise(item: dict, company_name: str, slug: str, today: str) -> dict | None:
    """
    Map a raw Lever posting dict to the DB schema.

    Returns None if the job does not match the keyword filter.
    """
    title = item.get("text") or ""
    additional = strip_html(item.get("additional") or item.get("description") or "")
    description = additional

    if not matches_keyword(title, description):
        return None

    categories = item.get("categories") or {}
    location_raw = categories.get("location") or ""

    posted_date = _epoch_ms_to_date(item.get("createdAt"), today)

    source_url = f"https://jobs.lever.co/{slug}"
    apply_url = item.get("hostedUrl") or source_url

    return {
        "title": title,
        "company": company_name,
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": _infer_job_type(location_raw),
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "apply_url": apply_url,
        "posted_date": posted_date,
        "fetched_date": today,
        "skills": _extract_skills(item),
        "experience_level": detect_experience_level(title, description),
        "role_type": detect_role_type(title),
    }


def _infer_job_type(location_raw: str) -> str:
    """Derive job_type from location string."""
    loc = location_raw.lower()
    if "remote" in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    return "onsite"


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant jobs from Lever ATS for all configured companies.

    Compliance:
    - 1 HTTP call per company slug.
    - 1-second sleep between company calls.
    - User-Agent header on every request.
    - apply_url links to the original job posting on jobs.lever.co.

    Returns:
        List of normalised job dicts ready for DB insertion.
    """
    today = date.today().isoformat()
    companies = load_companies("lever")
    jobs: list[dict] = []

    for i, company in enumerate(companies):
        if i > 0:
            time.sleep(1)

        slug = company["slug"]
        name = company["name"]

        try:
            raw_jobs = _fetch_company_jobs(slug)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                continue
            raise

        for item in raw_jobs:
            normalised = _normalise(item, name, slug, today)
            if normalised:
                jobs.append(normalised)

    return jobs

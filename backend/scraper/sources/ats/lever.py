import time
from datetime import datetime, timezone

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.sources.ats import fetch_ats_companies, strip_html
from scraper.tagger import tag_location

SOURCE_NAME = "Lever"
API_BASE = "https://api.lever.co/v0/postings"
# Companies hosted on Lever's EU instance return 404 from the US API.
API_BASE_EU = "https://api.eu.lever.co/v0/postings"
# Lever returns at most `limit` postings per call (default 100) — paginate.
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_WORKERS = 10
SLEEP_BETWEEN = 0.2

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def _fetch_from(base: str, slug: str) -> list[dict]:
    """
    Fetch every posting for a slug from one Lever region, paginating.

    Lever caps each response at `limit` postings (default 100), so large
    companies were previously truncated to their first 100 postings.

    Args:
        base: API base URL (US or EU).
        slug: Lever site identifier.

    Returns:
        Raw list of posting dicts.
    """
    postings: list[dict] = []
    for page in range(MAX_PAGES):
        response = requests.get(
            f"{base}/{slug}",
            headers=HEADERS,
            params={"mode": "json", "limit": PAGE_SIZE, "skip": page * PAGE_SIZE},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        batch = data if isinstance(data, list) else data.get("data", [])
        postings.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(SLEEP_BETWEEN)
    return postings


def _fetch_company_jobs(slug: str) -> list[dict]:
    """
    Fetch all open job postings for a single Lever company slug.

    Tries the US API first and falls back to the EU instance on 404.

    Args:
        slug: Lever posting identifier (e.g. 'grafanalabs').

    Returns:
        Raw list of posting dicts from the Lever API.
    """
    try:
        return _fetch_from(API_BASE, slug)
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
    time.sleep(SLEEP_BETWEEN)
    return _fetch_from(API_BASE_EU, slug)


def _location_raw(item: dict) -> str:
    """
    Combine every location a Lever posting lists into one string.

    Uses categories.location plus categories.allLocations, so a job posted
    for "San Francisco" and "Bengaluru" is tagged Bengaluru instead of being
    dropped as Global. Adds "India" when the country code is IN.
    """
    categories = item.get("categories") or {}
    locations: list[str] = []
    for loc in [categories.get("location")] + list(categories.get("allLocations") or []):
        if loc and loc not in locations:
            locations.append(loc)
    location_raw = "; ".join(locations)
    if (item.get("country") or "").upper() == "IN" and "india" not in location_raw.lower():
        location_raw = f"{location_raw}; India" if location_raw else "India"
    return location_raw


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

    location_raw = _location_raw(item)
    workplace = (item.get("workplaceType") or "").lower()

    posted_date = _epoch_ms_to_date(item.get("createdAt"), today)

    source_url = f"https://jobs.lever.co/{slug}"
    apply_url = item.get("hostedUrl") or source_url

    return {
        "title": title,
        "company": company_name,
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": workplace if workplace in ("remote", "hybrid", "onsite") else _infer_job_type(location_raw),
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


def _fetch_and_filter(company: dict, today: str) -> list[dict]:
    """
    Fetch and normalise jobs for one Lever company. Returns empty list on error.

    Intended for use inside a ThreadPoolExecutor worker.
    """
    slug = company["slug"]
    name = company["name"]
    time.sleep(SLEEP_BETWEEN)
    try:
        raw_jobs = _fetch_company_jobs(slug)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return []
        raise
    result = []
    for item in raw_jobs:
        normalised = _normalise(item, name, slug, today)
        if normalised:
            result.append(normalised)
    return result


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant jobs from Lever ATS for all configured companies.

    Compliance:
    - 1 HTTP call per company slug.
    - SLEEP_BETWEEN seconds between calls (enforced per worker via sleep in worker).
    - User-Agent header on every request.
    - apply_url links to the original job posting on jobs.lever.co.
    - Up to MAX_WORKERS companies fetched in parallel.
    - Cold slugs (no matching job recently) are polled weekly, not daily.

    Returns:
        List of normalised job dicts ready for DB insertion.
    """
    return fetch_ats_companies("lever", _fetch_and_filter, MAX_WORKERS)

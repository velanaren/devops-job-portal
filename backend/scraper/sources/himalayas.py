"""
Himalayas job source — remote-only job board.

API docs: https://himalayas.app/jobs/api
Browse : GET https://himalayas.app/jobs/api
Search : GET https://himalayas.app/jobs/api/search

Auth: none required.
Rate limit: data refreshes every 24 hours — one daily fetch is safe.
Pagination: offset + limit parameters, max 20 results per request.
"""

import time
from datetime import date, datetime, timezone

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.tagger import tag_location

SOURCE_NAME = "Himalayas"
SOURCE_URL = "https://himalayas.app"
SEARCH_URL = "https://himalayas.app/jobs/api/search"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

# One HTTP call per term, 1-second sleep between calls.
SEARCH_TERMS = [
    "devops",
    "sre",
    "platform engineer",
    "cloud engineer",
    "infrastructure engineer",
    "site reliability",
]

# Himalayas seniority field → DB experience_level mapping.
_SENIORITY_MAP: dict[str, str] = {
    "Entry-level": "entry",
    "Mid-level":   "mid",
    "Senior":      "senior",
    "Manager":     "staff",
    "Director":    "staff",
    "Executive":   "staff",
}


def _location_raw(restrictions: list[dict]) -> str:
    """
    Derive a location_raw string from the locationRestrictions array.

    Himalayas locationRestrictions semantics:
      []                    → work from anywhere worldwide
      [{"alpha2": "IN"}]    → remote from India only
      [{single country}]    → remote from that one country
      [{country1}, ...]     → multiple country restriction

    Args:
        restrictions: List of restriction dicts from the API response,
                      e.g. [{"alpha2": "IN", "name": "India"}].

    Returns:
        "Worldwide"        — empty restrictions (tagger → Remote Global).
        "India Remote"     — single IN restriction (tagger → Remote India).
        "{Country name}"   — single other country (tagger → Global).
        "Multiple regions" — two or more restrictions (tagger → Global).
    """
    if not restrictions:
        return "Worldwide"

    if len(restrictions) > 1:
        return "Multiple regions"

    entry = restrictions[0]
    alpha2 = (entry.get("alpha2") or "").upper()

    if alpha2 == "IN":
        return "India Remote"

    # Use the human-readable name if the API provides it; fall back to alpha2.
    return entry.get("name") or alpha2


def _parse_pubdate(pub_date, today: str) -> str:
    """
    Convert pubDate to an ISO date string (YYYY-MM-DD).

    Himalayas returns pubDate as a Unix timestamp in milliseconds.

    Args:
        pub_date: Unix timestamp in ms (int/float), ISO string, or None.
        today:    Fallback date string used when pub_date is absent or invalid.

    Returns:
        ISO date string YYYY-MM-DD.
    """
    if not pub_date:
        return today
    try:
        if isinstance(pub_date, (int, float)):
            ts_seconds = pub_date / 1000
            return datetime.fromtimestamp(ts_seconds, tz=timezone.utc).strftime("%Y-%m-%d")
        pub_str = str(pub_date)
        if len(pub_str) >= 10:
            return pub_str[:10]
    except Exception:
        pass
    return today


def _normalise(item: dict, today: str) -> dict | None:
    """
    Map a raw Himalayas job dict to the DB schema.

    Args:
        item:  Raw job dict from the API response.
        today: ISO date string for fetched_date.

    Returns:
        Normalised job dict ready for DB insertion, or None if the job does
        not pass the keyword filter.
    """
    title = item.get("title") or ""
    description = item.get("description") or ""

    if not matches_keyword(title, description):
        return None

    restrictions = item.get("locationRestrictions") or []
    loc_raw = _location_raw(restrictions)

    categories = item.get("categories") or []
    skills = ",".join(str(c) for c in categories if c)

    # Map seniority → experience_level; fall back to title/description inference.
    seniority = item.get("seniority") or ""
    experience = _SENIORITY_MAP.get(seniority) or detect_experience_level(title, description)

    return {
        "title":            title,
        "company":          item.get("companyName") or "",
        "location_raw":     loc_raw,
        "location_tag":     tag_location(loc_raw, SOURCE_NAME),
        "job_type":         "remote",
        "source_name":      SOURCE_NAME,
        "source_url":       SOURCE_URL,
        "apply_url":        item.get("applicationLink") or SOURCE_URL,
        "posted_date":      _parse_pubdate(item.get("pubDate"), today),
        "fetched_date":     today,
        "skills":           skills,
        "experience_level": experience,
        "role_type":        detect_role_type(title),
    }


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant jobs from Himalayas using keyword searches.

    Compliance:
    - 6 HTTP calls per daily run (one per SEARCH_TERMS entry).
    - User-Agent header on every request.
    - 1-second sleep between calls.
    - Deduplicates by job["guid"] within the run.
    - Never triggered from a web request — cron only.

    Returns:
        Deduplicated list of normalised job dicts ready for DB insertion.
    """
    today = date.today().isoformat()
    seen_guids: set[str] = set()
    jobs: list[dict] = []

    for i, term in enumerate(SEARCH_TERMS):
        if i > 0:
            time.sleep(1)

        response = requests.get(
            SEARCH_URL,
            headers=HEADERS,
            params={"q": term, "limit": 20, "offset": 0},
            timeout=30,
        )
        response.raise_for_status()

        raw_jobs = response.json().get("jobs") or []

        for item in raw_jobs:
            guid = item.get("guid") or ""
            if guid and guid in seen_guids:
                continue
            if guid:
                seen_guids.add(guid)

            normalised = _normalise(item, today)
            if normalised:
                jobs.append(normalised)

    return jobs

"""
Himalayas job source — remote-only job board.

API docs: https://himalayas.app/jobs/api
Browse : GET https://himalayas.app/jobs/api
Search : GET https://himalayas.app/jobs/api/search

Auth: none required.
Rate limit: data refreshes every 24 hours — one daily fetch is safe.
Pagination: offset + limit parameters, max 20 results per request.

Actual API field shapes (verified):
  locationRestrictions: list[str]   e.g. ["United States"] or []
  seniority:            list[str]   e.g. ["Senior"]
  pubDate:              int         Unix timestamp in milliseconds
  categories:           list[str]   e.g. ["Entry-Level-Python-Developer-AI-ML"]
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

# Himalayas seniority list item → DB experience_level mapping.
_SENIORITY_MAP: dict[str, str] = {
    "Entry-level": "entry",
    "Mid-level":   "mid",
    "Senior":      "senior",
    "Manager":     "staff",
    "Director":    "staff",
    "Executive":   "staff",
}


def _location_raw(restrictions: list) -> str:
    """
    Derive a location_raw string from the locationRestrictions array.

    Himalayas locationRestrictions is a list of plain country name strings.

      []                  → work from anywhere worldwide
      ["India"]           → remote from India only
      ["United States"]   → remote from that one country
      ["US", "Canada"]    → multiple country restrictions
      If India is in a multi-country list → still tag as India Remote

    Args:
        restrictions: List of country name strings from the API response,
                      e.g. ["United States"] or [].

    Returns:
        "Worldwide"        — empty list (tagger → Remote Global).
        "India Remote"     — India present in list (tagger → Remote India).
        "{Country name}"   — single non-India country (tagger → Global).
        "Multiple regions" — multiple non-India countries (tagger → Global).
    """
    if not restrictions:
        return "Worldwide"

    # India anywhere in the list → Remote India.
    if any(r.lower() == "india" for r in restrictions):
        return "India Remote"

    if len(restrictions) == 1:
        return restrictions[0]

    return "Multiple regions"


def _parse_pubdate(pub_date, today: str) -> str:
    """
    Convert pubDate (Unix timestamp in milliseconds) to an ISO date string.

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
            # Values > 1e10 are milliseconds (divide by 1000);
            # values <= 1e10 are already seconds (Himalayas actual format).
            ts_seconds = pub_date / 1000 if pub_date > 1e10 else pub_date
            return datetime.fromtimestamp(ts_seconds, tz=timezone.utc).date().isoformat()
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

    # ISSUE 1 fix: locationRestrictions is list[str], not list[dict].
    restrictions = item.get("locationRestrictions") or []
    loc_raw = _location_raw(restrictions)

    # ISSUE 4 fix: categories are hyphenated strings — clean before joining.
    categories = item.get("categories") or []
    skills = ", ".join(
        c.replace("-", " ").title()
        for c in categories
        if c
    )

    # ISSUE 2 fix: seniority is list[str], take first element if present.
    seniority_list = item.get("seniority") or []
    seniority = seniority_list[0] if seniority_list else ""
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
        # ISSUE 3 fix: pubDate is Unix ms timestamp — _parse_pubdate handles it.
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

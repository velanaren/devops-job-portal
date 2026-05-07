from datetime import date

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.tagger import tag_location

SOURCE_NAME = "Arbeitnow"
SOURCE_URL = "https://www.arbeitnow.com"
API_URL = "https://www.arbeitnow.com/api/job-board-api"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

MAX_PAGES = 5


def _fetch_page(page: int) -> tuple[list[dict], str | None]:
    """
    Fetch a single page of remote jobs from Arbeitnow.

    Args:
        page: 1-based page number.

    Returns:
        Tuple of (job list, next page URL or None).
    """
    response = requests.get(
        API_URL,
        headers=HEADERS,
        params={"remote": "true", "page": page},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("data", [])
    next_url = payload.get("links", {}).get("next")
    return jobs, next_url


def _normalise(item: dict, today: str) -> dict | None:
    """
    Map a raw Arbeitnow job dict to the DB schema.

    Returns None if the job does not match the keyword filter.
    """
    title = item.get("title") or ""
    description = item.get("description") or ""

    if not matches_keyword(title, description):
        return None

    location_raw = item.get("location") or ""
    is_remote = item.get("remote", False)
    if is_remote and not location_raw:
        location_raw = "Remote"

    tags = item.get("tags") or []
    skills = ",".join(str(t) for t in tags if t)

    created_at = item.get("created_at") or ""
    posted_date = created_at[:10] if len(created_at) >= 10 else today

    slug = item.get("slug") or ""
    apply_url = item.get("url") or (f"{SOURCE_URL}/jobs/{slug}" if slug else SOURCE_URL)

    return {
        "title": title,
        "company": item.get("company_name") or "",
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": "remote" if is_remote else "onsite",
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "apply_url": apply_url,
        "posted_date": posted_date,
        "fetched_date": today,
        "skills": skills,
        "experience_level": detect_experience_level(title, description),
        "role_type": detect_role_type(title),
    }


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant remote jobs from the Arbeitnow job board API.

    Compliance:
    - 1 call per daily run (up to MAX_PAGES pages within that run).
    - User-Agent header on every request.
    - Source attribution link back to Arbeitnow on every job card.

    Returns:
        List of normalised job dicts ready for DB insertion.
    """
    today = date.today().isoformat()
    jobs: list[dict] = []

    for page in range(1, MAX_PAGES + 1):
        raw_jobs, next_url = _fetch_page(page)

        for item in raw_jobs:
            normalised = _normalise(item, today)
            if normalised:
                jobs.append(normalised)

        if not next_url:
            break

    return jobs

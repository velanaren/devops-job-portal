import time
from datetime import date

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.tagger import tag_location

SOURCE_NAME = "Remotive"
SOURCE_URL = "https://remotive.com"
API_URL = "https://remotive.com/api/remote-jobs"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

# 4 grouped keyword searches — exactly 4 calls/day, within Remotive's limit.
# Terms are grouped by theme so each query covers multiple role categories.
SEARCH_TERMS = [
    "devops devsecops",
    "sre site reliability platform engineer",
    "cloud engineer infrastructure",
    "tech support it support mlops",
]


def _fetch_page(search: str) -> list[dict]:
    """
    Fetch one page of Remotive jobs for a given search term.

    Args:
        search: Keyword string to pass as the ?search= parameter.

    Returns:
        Raw list of job dicts from the API response.
    """
    response = requests.get(
        API_URL,
        headers=HEADERS,
        params={"search": search},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("jobs", [])


def _normalise(item: dict, today: str) -> dict | None:
    """
    Map a raw Remotive job dict to the DB schema.

    Returns None if the job does not match the keyword filter.
    """
    title = item.get("title") or ""
    description = item.get("description") or ""

    if not matches_keyword(title, description):
        return None

    location_raw = item.get("candidate_required_location") or "Worldwide"

    raw_type = (item.get("job_type") or "").lower()
    if "full" in raw_type or "part" in raw_type:
        job_type = "remote"
    else:
        job_type = "remote"

    tags = item.get("tags") or []
    skills = ",".join(str(t) for t in tags if t)

    pub_date = item.get("publication_date") or ""
    posted_date = pub_date[:10] if len(pub_date) >= 10 else today

    return {
        "title": title,
        "company": item.get("company_name") or "",
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": job_type,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "apply_url": item.get("url") or SOURCE_URL,
        "posted_date": posted_date,
        "fetched_date": today,
        "skills": skills,
        "experience_level": detect_experience_level(title, description),
        "role_type": detect_role_type(title),
    }


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant jobs from Remotive using multiple keyword searches.

    Compliance:
    - Maximum 4 HTTP calls per daily run (one per SEARCH_TERMS entry).
    - User-Agent header on every request.
    - 1-second sleep between calls to be respectful.
    - Jobs must not be placed behind email gating — Remotive API is open.

    Returns:
        Deduplicated list of normalised job dicts ready for DB insertion.
    """
    today = date.today().isoformat()
    seen_ids: set[int] = set()
    jobs: list[dict] = []

    for i, term in enumerate(SEARCH_TERMS):
        if i > 0:
            time.sleep(1)

        raw_jobs = _fetch_page(term)

        for item in raw_jobs:
            job_id = item.get("id")
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            normalised = _normalise(item, today)
            if normalised:
                jobs.append(normalised)

    return jobs

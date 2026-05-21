import time
from datetime import date

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.tagger import tag_location

SOURCE_NAME = "Jobicy"
SOURCE_URL = "https://jobicy.com"
API_URL = "https://jobicy.com/api/v2/remote-jobs"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

# One call per tag — 8 calls total, well within the 1/hour compliance limit.
SEARCH_TAGS = [
    "devops",
    "sre",
    "platform-engineer",
    "cloud-engineer",
    "infrastructure",
    "tech-support",
    "it-support",
    "mlops",
]


def _fetch_tag(tag: str) -> list[dict]:
    """
    Fetch up to 100 jobs from Jobicy for a single tag.

    Args:
        tag: Jobicy tag slug (e.g. 'devops', 'platform-engineer').

    Returns:
        Raw list of job dicts from the API response.
    """
    response = requests.get(
        API_URL,
        headers=HEADERS,
        params={"tag": tag, "count": 100},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("jobs", [])


def _normalise(item: dict, today: str) -> dict | None:
    """
    Map a raw Jobicy job dict to the DB schema.

    Returns None if the job does not match the keyword filter.
    """
    title = item.get("jobTitle") or ""
    description = item.get("jobDescription") or item.get("jobExcerpt") or ""

    if not matches_keyword(title, description):
        return None

    location_raw = item.get("jobGeo") or "Worldwide"

    raw_type = item.get("jobType") or ""
    if isinstance(raw_type, list):
        raw_type = " ".join(raw_type).lower()
    else:
        raw_type = raw_type.lower()
    job_type = "remote" if "remote" in raw_type else "onsite"

    tags = item.get("jobTags") or []
    if isinstance(tags, list):
        skills = ",".join(str(t) for t in tags if t)
    else:
        skills = str(tags)

    pub_date = item.get("pubDate") or ""
    posted_date = pub_date[:10] if len(pub_date) >= 10 else today

    job_id = item.get("id") or item.get("jobId") or ""
    apply_url = item.get("url") or (f"https://jobicy.com/jobs/{job_id}" if job_id else SOURCE_URL)

    return {
        "title": title,
        "company": item.get("companyName") or "",
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": job_type,
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
    Fetch DevOps-relevant jobs from the Jobicy API using per-tag queries.

    Compliance:
    - 8 HTTP calls per daily run — one per tag — well within 1/hour limit.
    - User-Agent header on every request.
    - 1-second sleep between calls to be respectful.
    - Results must not be redistributed to other job platforms.

    Returns:
        Deduplicated list of normalised job dicts ready for DB insertion.
    """
    today = date.today().isoformat()
    seen_ids: set = set()
    jobs: list[dict] = []

    for i, tag in enumerate(SEARCH_TAGS):
        if i > 0:
            time.sleep(1)

        raw_jobs = _fetch_tag(tag)

        for item in raw_jobs:
            job_id = item.get("id") or item.get("jobId")
            if job_id and job_id in seen_ids:
                continue
            if job_id:
                seen_ids.add(job_id)

            normalised = _normalise(item, today)
            if normalised:
                jobs.append(normalised)

    return jobs

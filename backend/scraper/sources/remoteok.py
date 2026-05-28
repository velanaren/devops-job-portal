import time
from datetime import date

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.tagger import tag_location

SOURCE_NAME = "RemoteOK"
SOURCE_URL = "https://remoteok.com"
API_URL = "https://remoteok.com/api"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant jobs from the RemoteOK public API.

    Compliance:
    - One HTTP call per daily run.
    - User-Agent header included on every request.
    - Every job card links back to RemoteOK via source_url.

    Returns:
        List of normalised job dicts ready for DB insertion.
        Returns empty list on error (caller should log separately).
    """
    response = requests.get(API_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    today = date.today().isoformat()
    jobs: list[dict] = []

    for item in data:
        # First element is a metadata object with slug "remoteok" — skip it.
        if not isinstance(item, dict) or item.get("slug") == "remoteok":
            continue

        title = item.get("position") or item.get("title") or ""
        description = item.get("description") or ""

        if not matches_keyword(title, description):
            continue

        location_raw = item.get("location") or "Worldwide"
        tags = item.get("tags") or []
        skills = ",".join(str(t) for t in tags if t)

        epoch = item.get("epoch") or item.get("date")
        try:
            posted_date = date.fromtimestamp(int(epoch)).isoformat() if epoch else today
        except (ValueError, OSError, TypeError):
            posted_date = today

        job_url = item.get("url") or f"{SOURCE_URL}/remote-jobs/{item.get('id', '')}"

        jobs.append({
            "title": title,
            "company": item.get("company") or "",
            "location_raw": location_raw,
            "location_tag": tag_location(location_raw, SOURCE_NAME),
            "job_type": "remote",
            "source_name": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "apply_url": job_url,
            "posted_date": posted_date,
            "fetched_date": today,
            "skills": skills,
            "experience_level": detect_experience_level(title, description),
            "role_type": detect_role_type(title),
        })

    return jobs

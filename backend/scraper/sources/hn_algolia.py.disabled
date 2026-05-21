import re
from datetime import date

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.tagger import tag_location

SOURCE_NAME = "HN"
SOURCE_URL = "https://news.ycombinator.com"
ALGOLIA_BASE = "https://hn.algolia.com/api/v1"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

# Typical HN comment format: "Company | Role | Location | ..."
_PIPE_SPLIT = re.compile(r"\s*\|\s*")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}")


def _find_hiring_thread_id() -> str | None:
    """
    Find the object ID of the most recent 'Ask HN: Who is Hiring?' story.

    Returns:
        Algolia object ID string, or None if not found.
    """
    url = f"{ALGOLIA_BASE}/search"
    params = {
        "query": "Ask HN: Who is Hiring?",
        "tags": "story",
        "hitsPerPage": 5,
    }
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    hits = response.json().get("hits", [])

    for hit in hits:
        title = hit.get("title", "")
        if "ask hn" in title.lower() and "who is hiring" in title.lower():
            return hit.get("objectID")
    return None


def _search_thread_comments(thread_id: str) -> list[dict]:
    """
    Search comments in the hiring thread for DevOps/remote job postings.

    Args:
        thread_id: Algolia object ID of the hiring thread story.

    Returns:
        List of raw comment hit dicts.
    """
    url = f"{ALGOLIA_BASE}/search"
    params = {
        "query": "devops OR sre OR platform OR cloud OR infrastructure OR remote",
        "tags": f"comment,story_{thread_id}",
        "hitsPerPage": 100,
    }
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("hits", [])


def _extract_url(text: str) -> str:
    """Extract the first URL found in text, or empty string."""
    match = _URL_PATTERN.search(text)
    return match.group(0) if match else ""


def _parse_comment(hit: dict, today: str) -> dict | None:
    """
    Parse a single HN comment into a normalised job dict.

    HN job comments are free-form text. We do best-effort parsing:
    - First line often contains: Company | Role | Location | [Remote/Onsite]
    - URL is extracted from anywhere in the comment.
    - Title defaults to the first line if no pipe-delimited fields.

    Returns None if the comment doesn't look like a relevant job posting.
    """
    text = hit.get("comment_text") or hit.get("story_text") or ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", text).strip()

    if not clean or len(clean) < 30:
        return None

    first_line = clean.split("\n")[0].strip()
    parts = _PIPE_SPLIT.split(first_line)

    company = parts[0].strip() if len(parts) >= 1 else ""
    title = parts[1].strip() if len(parts) >= 2 else first_line
    location_raw = parts[2].strip() if len(parts) >= 3 else "Remote"

    if not matches_keyword(title, clean):
        return None

    apply_url = _extract_url(clean)
    if not apply_url:
        hn_id = hit.get("objectID") or hit.get("story_id") or ""
        apply_url = f"{SOURCE_URL}/item?id={hn_id}" if hn_id else SOURCE_URL

    created_at = hit.get("created_at") or ""
    posted_date = created_at[:10] if len(created_at) >= 10 else today

    location_lower = location_raw.lower()
    if any(w in location_lower for w in ("remote", "anywhere", "worldwide")):
        job_type = "remote"
    elif "hybrid" in location_lower:
        job_type = "hybrid"
    else:
        job_type = "onsite"

    return {
        "title": title,
        "company": company,
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": job_type,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "apply_url": apply_url,
        "posted_date": posted_date,
        "fetched_date": today,
        "skills": "",
        "experience_level": detect_experience_level(title, clean),
        "role_type": detect_role_type(title),
    }


def fetch_jobs() -> list[dict]:
    """
    Fetch DevOps-relevant job postings from the current HN 'Who is Hiring' thread.

    Compliance:
    - 2 HTTP calls total (1 to find thread + 1 to search comments).
    - User-Agent header on every request.
    - Source attributed to Hacker News on every job card.
    - Only searches the 'Who is Hiring' thread — no other HN content.

    Returns:
        List of normalised job dicts parsed from HN comments.
        Returns empty list if the hiring thread cannot be found.
    """
    today = date.today().isoformat()

    thread_id = _find_hiring_thread_id()
    if not thread_id:
        return []

    comments = _search_thread_comments(thread_id)

    jobs: list[dict] = []
    for hit in comments:
        parsed = _parse_comment(hit, today)
        if parsed:
            jobs.append(parsed)

    return jobs

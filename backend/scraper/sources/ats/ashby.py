import time

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.sources.ats import fetch_ats_companies, strip_html
from scraper.tagger import tag_location

SOURCE_NAME = "Ashby"
API_BASE = "https://api.ashbyhq.com/posting-api/job-board"
MAX_WORKERS = 10
SLEEP_BETWEEN = 0.2

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def _fetch_company_jobs(slug: str) -> list[dict]:
    """
    Fetch all open job listings for a single Ashby company slug.

    Args:
        slug: Ashby listing identifier (e.g. 'tailscale').

    Returns:
        Raw list of job dicts from the Ashby API.
    """
    url = f"{API_BASE}/{slug}"
    params = {"includeCompensation": "true"}
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    # API returns "jobPostings" on some versions, "jobs" on others — handle both.
    return data.get("jobPostings", data.get("jobs", []))


def _location_text(loc) -> str:
    """Return a location's display string from a str or Ashby location dict."""
    if isinstance(loc, str):
        return loc
    if isinstance(loc, dict):
        text = loc.get("location") or loc.get("locationName") or loc.get("locationStr") or ""
        country = ((loc.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or ""
        if country and country.lower() not in text.lower():
            text = f"{text}, {country}" if text else country
        return text
    return ""


def _location_raw(item: dict) -> str:
    """
    Combine an Ashby job's primary and secondary locations into one string.

    Previously only the primary location was read, so a job listed in
    "San Francisco" with a secondary "Bengaluru" location was tagged Global
    and dropped. The tagger finds the India location in the combined string.
    """
    locations: list[str] = []
    primary_loc = item.get("locationName") or item.get("location")
    primary = primary_loc if isinstance(primary_loc, dict) else {
        "location": primary_loc,
        "address": item.get("address"),
    }
    for loc in [primary] + list(item.get("secondaryLocations") or []):
        text = _location_text(loc).strip(" ,")
        if text and text not in locations:
            locations.append(text)
    return "; ".join(locations)


def _normalise(item: dict, company_name: str, slug: str, today: str) -> dict | None:
    """
    Map a raw Ashby job dict to the DB schema.

    Returns None if the job does not match the keyword filter.
    """
    title = item.get("title") or ""
    description = strip_html(item.get("descriptionHtml") or item.get("description") or "")

    if not matches_keyword(title, description):
        return None

    if item.get("isListed") is False:
        return None

    is_remote = item.get("isRemote", False)
    location_raw = _location_raw(item)
    if is_remote and not location_raw:
        location_raw = "Remote"
    workplace = (item.get("workplaceType") or "").lower()

    published_at = item.get("publishedAt") or ""
    posted_date = published_at[:10] if len(published_at) >= 10 else today

    department = item.get("departmentName") or item.get("department") or ""

    source_url = f"https://jobs.ashbyhq.com/{slug}"
    apply_url = item.get("applyUrl") or item.get("jobUrl") or source_url

    return {
        "title": title,
        "company": company_name,
        "location_raw": location_raw,
        "location_tag": tag_location(location_raw, SOURCE_NAME),
        "job_type": (
            "remote" if is_remote or workplace == "remote"
            else "hybrid" if workplace == "hybrid"
            else _infer_job_type(location_raw)
        ),
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "apply_url": apply_url,
        "posted_date": posted_date,
        "fetched_date": today,
        "skills": department,
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
    Fetch and normalise jobs for one Ashby company. Returns empty list on error.

    Intended for use inside a ThreadPoolExecutor worker.
    """
    slug = company["slug"]
    name = company["name"]
    time.sleep(SLEEP_BETWEEN)
    try:
        raw_jobs = _fetch_company_jobs(slug)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (404, 403):
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
    Fetch DevOps-relevant jobs from Ashby ATS for all configured companies.

    Compliance:
    - 1 HTTP call per company slug.
    - SLEEP_BETWEEN seconds between calls (enforced per worker via sleep in worker).
    - User-Agent header on every request.
    - apply_url links to the original job posting on jobs.ashbyhq.com.
    - Up to MAX_WORKERS companies fetched in parallel.
    - Cold slugs (no matching job recently) are polled weekly, not daily.

    Returns:
        List of normalised job dicts ready for DB insertion.
    """
    return fetch_ats_companies("ashby", _fetch_and_filter, MAX_WORKERS)

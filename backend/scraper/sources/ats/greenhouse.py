import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import requests

from config.settings import USER_AGENT
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword
from scraper.sources.ats import load_companies, strip_html
from scraper.tagger import tag_location

SOURCE_NAME = "Greenhouse"
API_BASE = "https://boards-api.greenhouse.io/v1/boards"
MAX_WORKERS = 10
SLEEP_BETWEEN = 0.2

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def _fetch_company_jobs(slug: str) -> list[dict]:
    """
    Fetch all open jobs for a single Greenhouse company slug.

    Args:
        slug: Greenhouse board identifier (e.g. 'cloudflare').

    Returns:
        Raw list of job dicts from the Greenhouse API.
    """
    url = f"{API_BASE}/{slug}/jobs"
    response = requests.get(
        url,
        headers=HEADERS,
        params={"content": "true"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("jobs", [])


def _normalise(item: dict, company_name: str, slug: str, today: str) -> dict | None:
    """
    Map a raw Greenhouse job dict to the DB schema.

    Returns None if the job does not match the keyword filter.
    """
    title = item.get("title") or ""
    content_html = item.get("content") or ""
    description = strip_html(content_html)

    if not matches_keyword(title, description):
        return None

    location_raw = (item.get("location") or {}).get("name") or ""

    updated_at = item.get("updated_at") or ""
    posted_date = updated_at[:10] if len(updated_at) >= 10 else today

    departments = item.get("departments") or []
    dept_names = ",".join(d.get("name", "") for d in departments if d.get("name"))

    source_url = f"https://boards.greenhouse.io/{slug}"
    apply_url = item.get("absolute_url") or source_url

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
        "skills": dept_names,
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
    Fetch and normalise jobs for one Greenhouse company. Returns empty list on error.

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
    Fetch DevOps-relevant jobs from Greenhouse ATS for all configured companies.

    Compliance:
    - 1 HTTP call per company slug.
    - SLEEP_BETWEEN seconds between calls (enforced per worker via sleep in worker).
    - User-Agent header on every request.
    - apply_url links to the original job posting on Greenhouse.
    - Up to MAX_WORKERS companies fetched in parallel.

    Returns:
        List of normalised job dicts ready for DB insertion.
    """
    today = date.today().isoformat()
    companies = load_companies("greenhouse")
    jobs: list[dict] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_and_filter, c, today): c for c in companies}
        for future in as_completed(futures):
            try:
                jobs.extend(future.result())
            except Exception:
                pass  # orchestrator handles per-source logging; skip bad slugs

    return jobs

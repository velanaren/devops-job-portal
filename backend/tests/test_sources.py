"""Tests for source parsing and pagination (no network — requests is mocked)."""
from unittest.mock import MagicMock, patch

import requests

from scraper.sources import himalayas
from scraper.sources.ats import ashby, lever

TODAY = "2026-10-03"


def _resp(payload, status=200):
    """Build a fake requests.Response-like object."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    if status >= 400:
        err = requests.HTTPError(response=r)
        r.raise_for_status.side_effect = err
    return r


# --- Himalayas ------------------------------------------------------------

def test_himalayas_paginates_until_short_page(monkeypatch):
    monkeypatch.setattr(himalayas, "SEARCH_TERMS", ["support engineer"])
    monkeypatch.setattr(himalayas, "SLEEP_BETWEEN", 0)
    page = lambda start, n: {"jobs": [
        {"guid": f"g{i}", "title": "Technical Support Engineer", "companyName": "X",
         "locationRestrictions": ["India"], "pubDate": 1759449600}
        for i in range(start, start + n)
    ]}
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(params["offset"])
        return _resp(page(params["offset"], 20 if params["offset"] < 40 else 5))

    with patch.object(himalayas.requests, "get", side_effect=fake_get):
        jobs = himalayas.fetch_jobs()
    assert calls == [0, 20, 40]
    assert len(jobs) == 45


def test_himalayas_stops_at_page_cap(monkeypatch):
    monkeypatch.setattr(himalayas, "SEARCH_TERMS", ["devops"])
    monkeypatch.setattr(himalayas, "SLEEP_BETWEEN", 0)
    monkeypatch.setattr(himalayas, "MAX_PAGES_PER_TERM", 2)

    def fake_get(url, headers, params, timeout):
        o = params["offset"]
        return _resp({"jobs": [{"guid": f"g{o + i}", "title": "DevOps Engineer"} for i in range(20)]})

    with patch.object(himalayas.requests, "get", side_effect=fake_get) as g:
        himalayas.fetch_jobs()
    assert g.call_count == 2


# --- Lever ----------------------------------------------------------------

def test_lever_paginates_past_100(monkeypatch):
    monkeypatch.setattr(lever, "SLEEP_BETWEEN", 0)

    def fake_get(url, headers, params, timeout):
        n = 100 if params["skip"] == 0 else 30
        return _resp([{"id": f"{params['skip']}-{i}"} for i in range(n)])

    with patch.object(lever.requests, "get", side_effect=fake_get):
        assert len(lever._fetch_company_jobs("acme")) == 130


def test_lever_falls_back_to_eu_on_404(monkeypatch):
    monkeypatch.setattr(lever, "SLEEP_BETWEEN", 0)
    urls = []

    def fake_get(url, headers, params, timeout):
        urls.append(url)
        return _resp([], 404) if "api.lever.co" in url else _resp([{"id": "eu1"}])

    with patch.object(lever.requests, "get", side_effect=fake_get):
        assert lever._fetch_company_jobs("acme") == [{"id": "eu1"}]
    assert "api.eu.lever.co" in urls[-1]


def test_lever_uses_all_locations():
    item = {
        "text": "Application Support Engineer",
        "categories": {"location": "San Francisco, CA", "allLocations": ["San Francisco, CA", "Bengaluru"]},
        "workplaceType": "hybrid",
        "hostedUrl": "https://jobs.lever.co/acme/1",
    }
    job = lever._normalise(item, "Acme", "acme", TODAY)
    assert job["location_tag"] == "Bengaluru"
    assert job["job_type"] == "hybrid"


def test_lever_country_code_india():
    item = {"text": "Support Engineer", "categories": {"location": "Remote"}, "country": "IN"}
    assert lever._normalise(item, "Acme", "acme", TODAY)["location_tag"] == "Remote India"


# --- Ashby ----------------------------------------------------------------

def test_ashby_uses_secondary_locations():
    item = {
        "title": "Technical Support Engineer",
        "location": "New York",
        "secondaryLocations": [{"location": "Hyderabad", "address": {"postalAddress": {"addressCountry": "India"}}}],
        "isListed": True,
        "jobUrl": "https://jobs.ashbyhq.com/acme/1",
    }
    assert ashby._normalise(item, "Acme", "acme", TODAY)["location_tag"] == "Hyderabad"


def test_ashby_skips_unlisted():
    item = {"title": "Support Engineer", "location": "Bengaluru", "isListed": False}
    assert ashby._normalise(item, "Acme", "acme", TODAY) is None


def test_ashby_old_location_dict_shape():
    item = {"title": "Support Engineer", "location": {"locationStr": "Pune, India"}}
    assert ashby._normalise(item, "Acme", "acme", TODAY)["location_tag"] == "Pune"

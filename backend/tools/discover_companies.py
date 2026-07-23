"""
One-time discovery script — find companies with relevant DevOps/SRE/Infra jobs.

Reads large ATS slug lists, tests each slug against the respective API,
and keeps only companies that have at least one job matching our role keywords
AND located in India or accessible remotely.

Usage:
    cd backend
    python3 -m tools.discover_companies

NOTE: Delete discover_checkpoint.json before each fresh run.

Output files (all gitignored — manual review before merging):
    backend/tools/discovered_companies.yaml  — companies to review
    backend/tools/discover_summary.txt       — run statistics
    backend/tools/discover_checkpoint.json   — checkpoint for resume
                                               (also stores found companies
                                                to survive interruption)

Input files:
    backend/tools/input/greenhouse_slugs.txt
    backend/tools/input/lever_slugs.txt
    backend/tools/input/ashby_slugs.txt
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_TOOLS_DIR = Path(__file__).parent
_INPUT_DIR = _TOOLS_DIR / "input"

GREENHOUSE_SLUGS_PATH = _INPUT_DIR / "greenhouse_slugs.txt"
LEVER_SLUGS_PATH = _INPUT_DIR / "lever_slugs.txt"
ASHBY_SLUGS_PATH = _INPUT_DIR / "ashby_slugs.txt"

CHECKPOINT_PATH = _TOOLS_DIR / "discover_checkpoint.json"
OUTPUT_YAML_PATH = _TOOLS_DIR / "discovered_companies.yaml"
SUMMARY_PATH = _TOOLS_DIR / "discover_summary.txt"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "InfraJobs/1.0 (personal project; contact: svelayuthamnaren@gmail.com)",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 15
SLEEP_BETWEEN = 1.0
CHECKPOINT_EVERY = 50

# ---------------------------------------------------------------------------
# Role keyword matching (mirrors scraper/filters.py)
# ---------------------------------------------------------------------------

_STRICT_ROLE_PATTERNS: list[str] = [
    r"\bdevops\b", r"\bdev ops\b", r"\bdevsecops\b", r"\bgitops\b",
    r"\baiops\b", r"\bdataops\b",
    r"\bsre\b", r"\bsite reliability\b", r"\breliability engineer\b",
    r"\bproduction engineer\b", r"\bdatabase reliability\b",
    r"\bplatform engineer\b", r"\bplatform engineering\b", r"\bplatform operations\b",
    r"\bcloud engineer\b", r"\bcloud infrastructure\b", r"\bcloud operations\b",
    r"\bcloud platform\b", r"\bcloud administrator\b", r"\bcloud architect\b",
    r"\baws engineer\b", r"\bazure engineer\b", r"\bgcp engineer\b", r"\bcloud devops\b",
    r"\binfrastructure engineer\b", r"\binfra engineer\b",
    r"\bsystems engineer\b", r"\bsystems administrator\b", r"\bsysadmin\b",
    r"\bnetwork engineer\b", r"\bnetwork operations\b",
    r"\bit infrastructure\b", r"\blinux administrator\b", r"\bnetwork administrator\b",
    r"\blinux engineer\b", r"\binfrastructure operations\b",
    r"\brelease engineer\b", r"\bbuild engineer\b", r"\bci/cd engineer\b",
    r"\bobservability engineer\b", r"\bmonitoring engineer\b",
    r"\bmlops\b", r"\bml engineer\b", r"\bml infrastructure\b", r"\bml platform\b",
    r"\bai platform\b", r"\bai infrastructure\b", r"\bllmops\b",
    r"\bapplication support\b", r"\bapp support\b",
    r"\bproduction support\b", r"\bprod support\b", r"\bplatform support\b",
    r"\bsoftware support\b", r"\bops support\b", r"\boperations support\b",
    r"\btech support\b", r"\btechnical support\b",
    r"\bsupport engineer\b", r"\bnoc engineer\b", r"\bnoc analyst\b",
    r"\btier 1 support\b", r"\btier 2 support\b", r"\btier 3 support\b",
    r"\bit support\b", r"\bl1 support\b", r"\bl2 support\b", r"\bl3 support\b",
    r"\bservice desk\b", r"\bhelpdesk\b", r"\bhelp desk\b",
    r"\bit operations\b", r"\bitops\b", r"\boperations engineer\b",
    r"\bdatabase administrator\b", r"\bdba\b",
]

_KEYWORD_RE = re.compile("|".join(_STRICT_ROLE_PATTERNS), re.IGNORECASE)


def _strip_html(html: str) -> str:
    """Remove HTML tags, returning plain text."""
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _matches_keyword(title: str, description: str = "") -> bool:
    """Return True if title (or fallback description) matches a role keyword."""
    if _KEYWORD_RE.search(title):
        return True
    if description and _KEYWORD_RE.search(description):
        return True
    return False


# ---------------------------------------------------------------------------
# Inclusive location detection for discovery
#
# Deliberately broad: "Remote" alone passes, empty location passes.
# The production tagger handles display-layer filtering.
# ---------------------------------------------------------------------------

_INDIA_TERMS: list[str] = [
    "india", "bengaluru", "bangalore", "chennai",
    "hyderabad", "mumbai", "pune", "delhi", "noida",
    "gurugram", "gurgaon", "kolkata", "kochi",
    "coimbatore", "trivandrum", "ahmedabad",
]

_REMOTE_TERMS: list[str] = [
    "remote", "anywhere", "worldwide", "work from anywhere",
    "wfa", "global", "distributed", "location independent",
    "no location", "fully remote",
]


def _is_relevant_location(location_raw: str) -> bool:
    """
    Return True if this raw location string suggests the job is accessible
    from India (either India-based or any kind of remote).

    Intentionally inclusive — the production tagger handles display filtering.
    Empty location is included (could be remote-by-default).
    """
    loc = location_raw.lower().strip()

    if not loc:
        return True

    if any(term in loc for term in _INDIA_TERMS):
        return True

    if any(term in loc for term in _REMOTE_TERMS):
        return True

    return False


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint() -> tuple[dict, list[dict]]:
    """
    Load checkpoint file.

    Returns:
        (checkpoint_state, found) where found is the list of companies
        discovered so far (stored inside the checkpoint to survive interruption).
    """
    if CHECKPOINT_PATH.exists():
        try:
            with open(CHECKPOINT_PATH) as f:
                state = json.load(f)
            found = state.pop("found", [])
            return state, found
        except Exception:
            pass
    return {"greenhouse": [], "lever": [], "ashby": [], "done": []}, []


def _save_checkpoint(state: dict, found: list[dict]) -> None:
    """Persist checkpoint and current found list to disk."""
    state["found"] = [dict(c) for c in found]
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# ATS fetchers
# ---------------------------------------------------------------------------

def _fetch_greenhouse(slug: str) -> list[dict]:
    """
    Fetch jobs from Greenhouse for a company slug.

    Returns list of normalised dicts with keys: title, location_raw, description.
    Returns empty list on any error.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = data.get("jobs", [])
        result = []
        for item in items:
            title = item.get("title") or ""
            description = _strip_html(item.get("content") or "")
            location_raw = (item.get("location") or {}).get("name") or ""
            result.append({"title": title, "location_raw": location_raw, "description": description})
        return result
    except Exception:
        return []


def _fetch_lever(slug: str) -> list[dict]:
    """
    Fetch jobs from Lever for a company slug.

    Returns list of normalised dicts. Returns empty list on error.
    """
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        result = []
        for item in items:
            title = item.get("text") or ""
            description = _strip_html(item.get("additional") or item.get("description") or "")
            location_raw = (item.get("categories") or {}).get("location") or ""
            result.append({"title": title, "location_raw": location_raw, "description": description})
        return result
    except Exception:
        return []


def _fetch_ashby(slug: str) -> list[dict]:
    """
    Fetch jobs from Ashby for a company slug.

    Returns list of normalised dicts. Returns empty list on error.
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = data.get("jobs", [])
        result = []
        for item in items:
            title = item.get("title") or ""
            description = _strip_html(item.get("descriptionHtml") or item.get("description") or "")
            is_remote = item.get("isRemote", False)
            location_raw = item.get("location") or item.get("locationName") or ""
            if is_remote and not location_raw:
                location_raw = "Remote"
            result.append({"title": title, "location_raw": location_raw, "description": description})
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Per-source discovery
# ---------------------------------------------------------------------------

def _get_relevant_job(jobs: list[dict]) -> dict | None:
    """
    Return the first job that matches keyword AND relevant location,
    or None if no match. Used to record a sample match in the output.
    """
    for job in jobs:
        if not _matches_keyword(job["title"], job["description"]):
            continue
        if _is_relevant_location(job["location_raw"]):
            return job
    return None


def _discover_source(
    ats: str,
    slugs: list[str],
    fetcher,
    already_done: list[str],
    found: list[dict],
    checkpoint_state: dict,
) -> list[dict]:
    """
    Iterate slugs for one ATS source. Checkpoints every CHECKPOINT_EVERY slugs.

    Args:
        ats:               ATS key ('greenhouse', 'lever', 'ashby').
        slugs:             Full slug list to process.
        fetcher:           Function slug -> list[dict].
        already_done:      Slugs already tested (from checkpoint).
        found:             Accumulated results list (mutated in place).
        checkpoint_state:  Full checkpoint dict (mutated in place).

    Returns:
        The found list (same object as passed in).
    """
    done_set = set(already_done)
    pending = [s for s in slugs if s not in done_set]
    total = len(slugs)
    processed_this_run = 0

    print(f"\n[{ats}] {len(pending)} slugs remaining ({len(done_set)} already done, {total} total)")

    for slug in pending:
        try:
            jobs = fetcher(slug)
            match = _get_relevant_job(jobs) if jobs else None
            if match:
                found.append({
                    "name": slug,
                    "ats": ats,
                    "slug": slug,
                    "sample_title": match["title"],
                    "sample_location": match["location_raw"],
                })
                print(f"  KEEP  {slug} ({ats}) — {match['title']!r} @ {match['location_raw']!r}")
        except Exception as e:
            print(f"  ERROR {slug}: {e}", file=sys.stderr)

        checkpoint_state[ats].append(slug)
        processed_this_run += 1

        if processed_this_run % CHECKPOINT_EVERY == 0:
            _save_checkpoint(checkpoint_state, found)
            done_count = len(checkpoint_state[ats])
            print(f"  [{ats}] checkpoint saved — {done_count}/{total} done, {len(found)} kept so far")

        time.sleep(SLEEP_BETWEEN)

    # Final checkpoint after source completes.
    _save_checkpoint(checkpoint_state, found)
    checkpoint_state["done"].append(ats)
    _save_checkpoint(checkpoint_state, found)
    print(f"[{ats}] done — kept {sum(1 for c in found if c['ats'] == ats)} companies")
    return found


# ---------------------------------------------------------------------------
# Slug reader
# ---------------------------------------------------------------------------

def _read_slugs(path: Path) -> list[str]:
    """Read slugs from a text file, one per line. Skip blanks."""
    if not path.exists():
        print(f"WARNING: slug file not found: {path}", file=sys.stderr)
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_output(found: list[dict], stats: dict) -> None:
    """Write discovered_companies.yaml and discover_summary.txt."""
    by_ats: dict[str, list[dict]] = {"greenhouse": [], "lever": [], "ashby": []}
    for company in found:
        by_ats[company["ats"]].append(company)

    with open(OUTPUT_YAML_PATH, "w") as f:
        f.write("# DISCOVERY OUTPUT — review before merging into companies.yaml\n")
        f.write(f"# Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
        f.write(f"# Total found: {len(found)}\n\n")
        yaml.dump({"companies": found}, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    with open(SUMMARY_PATH, "w") as f:
        f.write("=== InfraJobs Company Discovery Summary ===\n")
        f.write(f"Run at: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n")
        for ats in ("greenhouse", "lever", "ashby"):
            total = stats.get(f"{ats}_total", 0)
            kept = len(by_ats[ats])
            tested = stats.get(f"{ats}_tested", total)
            f.write(f"{ats.upper()}\n")
            f.write(f"  Slugs tested : {tested}\n")
            f.write(f"  Companies kept: {kept}\n")
            f.write(f"  Pass rate   : {kept/tested*100:.1f}%\n" if tested else "  Pass rate   : —\n")
            f.write("\n")
        f.write(f"TOTAL COMPANIES FOUND: {len(found)}\n")
        f.write(f"Output: {OUTPUT_YAML_PATH}\n")

    print(f"\nOutput written to:\n  {OUTPUT_YAML_PATH}\n  {SUMMARY_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the discovery script."""
    print("=== InfraJobs Company Discovery ===")
    print("Location filter: India terms + any remote term + empty location")
    print(f"Checkpoint: {CHECKPOINT_PATH}")

    checkpoint_state, found = _load_checkpoint()
    done_sources = set(checkpoint_state.get("done", []))

    if found:
        print(f"Resuming — {len(found)} companies already found in checkpoint")

    stats: dict = {}

    sources = [
        ("greenhouse", GREENHOUSE_SLUGS_PATH, _fetch_greenhouse),
        ("lever",      LEVER_SLUGS_PATH,      _fetch_lever),
        ("ashby",      ASHBY_SLUGS_PATH,      _fetch_ashby),
    ]

    for ats, path, fetcher in sources:
        slugs = _read_slugs(path)
        stats[f"{ats}_total"] = len(slugs)
        stats[f"{ats}_tested"] = len(slugs)

        if ats in done_sources:
            print(f"\n[{ats}] already complete — skipping")
            continue

        already_done = checkpoint_state.get(ats, [])
        _discover_source(ats, slugs, fetcher, already_done, found, checkpoint_state)

    _write_output(found, stats)

    print(f"\n=== Discovery complete — {len(found)} companies found ===")
    print("Review discovered_companies.yaml before merging into companies.yaml")


if __name__ == "__main__":
    main()

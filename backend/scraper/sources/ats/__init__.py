import re
from pathlib import Path

import yaml

from config.settings import COMPANIES_YAML_PATH

_SLUGS_DIR = Path(__file__).parent.parent.parent.parent / "config" / "slugs"


def load_companies(ats: str) -> list[dict]:
    """
    Return companies for the given ATS.

    Prefers backend/config/slugs/{ats}_slugs.txt (one slug per line) when that
    file exists, because it may contain many more entries than companies.yaml.
    Falls back to companies.yaml entries when the slug file is absent.

    Args:
        ats: ATS identifier — 'greenhouse', 'lever', or 'ashby'.

    Returns:
        List of dicts with keys: name, ats, slug.
        When loaded from the slug file, name == slug (display name unknown).
    """
    slug_file = _SLUGS_DIR / f"{ats}_slugs.txt"

    if slug_file.exists():
        slugs = [line.strip() for line in slug_file.read_text().splitlines() if line.strip()]
        return [{"name": s, "ats": ats, "slug": s} for s in slugs]

    # Fallback — curated companies.yaml list.
    with open(COMPANIES_YAML_PATH) as f:
        data = yaml.safe_load(f)
    return [c for c in data.get("companies", []) if c.get("ats") == ats]


def strip_html(html: str) -> str:
    """Remove HTML tags from a string, returning plain text."""
    return re.sub(r"<[^>]+>", " ", html or "").strip()

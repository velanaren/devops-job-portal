import re

import yaml

from config.settings import COMPANIES_YAML_PATH


def load_companies(ats: str) -> list[dict]:
    """
    Return all companies from companies.yaml that use the given ATS.

    Args:
        ats: ATS identifier — 'greenhouse', 'lever', or 'ashby'.

    Returns:
        List of company dicts with keys: name, ats, slug.
    """
    with open(COMPANIES_YAML_PATH) as f:
        data = yaml.safe_load(f)
    return [c for c in data.get("companies", []) if c.get("ats") == ats]


def strip_html(html: str) -> str:
    """Remove HTML tags from a string, returning plain text."""
    return re.sub(r"<[^>]+>", " ", html or "").strip()

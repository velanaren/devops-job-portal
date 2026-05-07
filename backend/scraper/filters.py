import re

KEYWORDS: list[str] = [
    "devops",
    "dev ops",
    "devsecops",
    "sre",
    "site reliability",
    "platform engineer",
    "platform engineering",
    "infrastructure engineer",
    "infra engineer",
    "cloud engineer",
    "cloud infrastructure",
    "application support",
    "app support",
    "tech support",
    "technical support",
    "l1 support",
    "l2 support",
    "l3 support",
    "systems engineer",
    "operations engineer",
    "release engineer",
    "build engineer",
]

# Maps internal role_type value to the title/description keywords that identify it.
ROLE_TYPE_MAP: dict[str, list[str]] = {
    "devops": ["devops", "dev ops", "devsecops"],
    "sre": ["sre", "site reliability"],
    "platform": ["platform engineer", "platform engineering"],
    "cloud": ["cloud engineer", "cloud infrastructure"],
    "appsupport": ["application support", "app support"],
    "techsupport": [
        "tech support",
        "technical support",
        "l1 support",
        "l2 support",
        "l3 support",
    ],
}

_SENIOR_PATTERNS: list[str] = [
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\blead\b",
    r"\bdirector\b",
    r"\bvp\b",
    r"\bhead of\b",
]
_SENIOR_LEVEL_PATTERNS: list[str] = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\biii\b",
]
_ENTRY_PATTERNS: list[str] = [
    r"\bjunior\b",
    r"\bjr\.?\b",
    r"\bentry[\s\-]level\b",
    r"\bassociate\b",
    r"\bgraduate\b",
    r"\bintern\b",
    r"\bi\b",
]


def _normalise(text: str) -> str:
    """Lower-case and collapse whitespace for consistent matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def matches_keyword(title: str, description: str = "") -> bool:
    """
    Return True if the job title or description contains at least one DevOps keyword.

    Args:
        title: Job title string.
        description: Optional job description text.

    Returns:
        True if a keyword match is found, False otherwise.
    """
    haystack = _normalise(f"{title} {description}")
    return any(kw in haystack for kw in KEYWORDS)


def detect_role_type(title: str) -> str:
    """
    Detect the primary role type from a job title.

    Checks role types in priority order: devops → sre → platform → cloud →
    appsupport → techsupport.

    Args:
        title: Job title string.

    Returns:
        One of: 'devops', 'sre', 'platform', 'cloud', 'appsupport', 'techsupport'.
        Returns 'devops' as a fallback if no specific match is found.
    """
    normalised = _normalise(title)
    for role_type, keywords in ROLE_TYPE_MAP.items():
        if any(kw in normalised for kw in keywords):
            return role_type
    return "devops"


def detect_experience_level(title: str, description: str = "") -> str:
    """
    Detect experience level from title and description using keyword heuristics.

    Args:
        title: Job title string.
        description: Optional job description text.

    Returns:
        One of: 'staff', 'senior', 'entry', 'mid'.
    """
    haystack = _normalise(f"{title} {description}")

    if any(re.search(p, haystack) for p in _SENIOR_PATTERNS):
        return "staff"
    if any(re.search(p, haystack) for p in _SENIOR_LEVEL_PATTERNS):
        return "senior"
    if any(re.search(p, haystack) for p in _ENTRY_PATTERNS):
        return "entry"
    return "mid"

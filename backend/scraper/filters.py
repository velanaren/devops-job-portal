import re

# ---------------------------------------------------------------------------
# Strict role keyword patterns — word-boundary matched, case-insensitive.
# Generic terms (engineer, cloud, support alone) are excluded to prevent
# false-positive matches.
# ---------------------------------------------------------------------------

_STRICT_ROLE_PATTERNS: list[str] = [
    # DevOps / GitOps
    r"\bdevops\b",
    r"\bdev ops\b",
    r"\bdevsecops\b",
    r"\bgitops\b",
    # SRE
    r"\bsre\b",
    r"\bsite reliability\b",
    r"\breliability engineer\b",
    r"\bproduction engineer\b",
    # Platform
    r"\bplatform engineer\b",
    r"\bplatform engineering\b",
    r"\bplatform operations\b",
    # Cloud
    r"\bcloud engineer\b",
    r"\bcloud infrastructure\b",
    r"\bcloud operations\b",
    r"\bcloud platform\b",
    r"\bcloud administrator\b",
    # Infrastructure / Systems / Network
    r"\binfrastructure engineer\b",
    r"\binfra engineer\b",
    r"\bsystems engineer\b",
    r"\bsystems administrator\b",
    r"\bsysadmin\b",
    r"\bnetwork engineer\b",
    r"\bnetwork operations\b",
    # CI/CD / Release
    r"\brelease engineer\b",
    r"\bbuild engineer\b",
    r"\bci/cd engineer\b",
    # Observability
    r"\bobservability engineer\b",
    r"\bmonitoring engineer\b",
    # MLOps / ML Infrastructure
    r"\bmlops\b",
    r"\bml engineer\b",
    r"\bml infrastructure\b",
    r"\bml platform\b",
    # Application / Tech Support
    r"\bapplication support\b",
    r"\bapp support\b",
    r"\btech support\b",
    r"\btechnical support\b",
    r"\bit support\b",
    r"\bl1 support\b",
    r"\bl2 support\b",
    r"\bl3 support\b",
    r"\bservice desk\b",
    r"\bhelpdesk\b",
    r"\bhelp desk\b",
    # IT Operations / DBA
    r"\bit operations\b",
    r"\bitops\b",
    r"\boperations engineer\b",
    r"\bdatabase administrator\b",
    r"\bdba\b",
]

_STRICT_KEYWORD_RE = re.compile("|".join(_STRICT_ROLE_PATTERNS), re.IGNORECASE)

# Maps internal role_type value to the patterns that identify it.
# Priority: first match wins — order matters.
ROLE_TYPE_MAP: dict[str, list[str]] = {
    "devops": [
        r"\bdevops\b",
        r"\bdev ops\b",
        r"\bdevsecops\b",
        r"\bgitops\b",
        r"\brelease engineer\b",
        r"\bbuild engineer\b",
        r"\bci/cd engineer\b",
    ],
    "sre": [
        r"\bsre\b",
        r"\bsite reliability\b",
        r"\breliability engineer\b",
        r"\bproduction engineer\b",
    ],
    "platform": [
        r"\bplatform engineer\b",
        r"\bplatform engineering\b",
        r"\bplatform operations\b",
    ],
    "cloud": [
        r"\bcloud engineer\b",
        r"\bcloud infrastructure\b",
        r"\bcloud operations\b",
        r"\bcloud platform\b",
        r"\bcloud administrator\b",
    ],
    "infra": [
        r"\binfrastructure engineer\b",
        r"\binfra engineer\b",
        r"\bsystems engineer\b",
        r"\bsystems administrator\b",
        r"\bsysadmin\b",
        r"\bnetwork engineer\b",
        r"\bnetwork operations\b",
        r"\bobservability engineer\b",
        r"\bmonitoring engineer\b",
    ],
    "mlops": [
        r"\bmlops\b",
        r"\bml engineer\b",
        r"\bml infrastructure\b",
        r"\bml platform\b",
    ],
    "appsupport": [
        r"\bapplication support\b",
        r"\bapp support\b",
    ],
    "techsupport": [
        r"\btech support\b",
        r"\btechnical support\b",
        r"\bit support\b",
        r"\bl1 support\b",
        r"\bl2 support\b",
        r"\bl3 support\b",
        r"\bservice desk\b",
        r"\bhelpdesk\b",
        r"\bhelp desk\b",
    ],
    "itops": [
        r"\bit operations\b",
        r"\bitops\b",
        r"\boperations engineer\b",
        r"\bdatabase administrator\b",
        r"\bdba\b",
    ],
}

_ROLE_TYPE_COMPILED: dict[str, re.Pattern] = {
    role: re.compile("|".join(patterns), re.IGNORECASE)
    for role, patterns in ROLE_TYPE_MAP.items()
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
    Return True if the job title contains at least one strict role keyword.

    Title is the primary check — a word-boundary regex match against the
    curated role keyword list. Description is used as a fallback only (for
    ATS sources where job titles may be generic). Generic terms such as
    'engineer', 'cloud', or 'support' alone do NOT match.

    Args:
        title:       Job title string.
        description: Optional job description text (fallback only).

    Returns:
        True if a strict keyword match is found, False otherwise.
    """
    if _STRICT_KEYWORD_RE.search(title):
        return True
    if description and _STRICT_KEYWORD_RE.search(description):
        return True
    return False


def detect_role_type(title: str) -> str:
    """
    Detect the primary role type from a job title using strict keyword patterns.

    Checks role types in priority order:
      devops → sre → platform → cloud → infra → mlops →
      appsupport → techsupport → itops

    Args:
        title: Job title string.

    Returns:
        One of: 'devops', 'sre', 'platform', 'cloud', 'infra', 'mlops',
        'appsupport', 'techsupport', 'itops'. Returns 'other' if no pattern
        matches — the orchestrator discards jobs with role_type 'other'.
    """
    for role_type, pattern in _ROLE_TYPE_COMPILED.items():
        if pattern.search(title):
            return role_type
    return "other"


def detect_experience_level(title: str, description: str = "") -> str:
    """
    Detect experience level from title and description using keyword heuristics.

    Args:
        title:       Job title string.
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

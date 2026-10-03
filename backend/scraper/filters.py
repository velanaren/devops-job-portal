import re

from config.settings import INCLUDE_HELPDESK

# ---------------------------------------------------------------------------
# Role keyword patterns — word-boundary matched, case-insensitive, applied to
# the job TITLE only. Descriptions are not used: role_type is derived from
# the title, so a description-only match would be classified 'other' and
# dropped anyway.
#
# Generic terms (engineer, cloud, support, platform alone) never match.
# Ambiguous phrases are qualified (e.g. "systems engineer" needs an infra
# qualifier) and EXCLUDE_PATTERNS removes known false positives.
# ---------------------------------------------------------------------------

# Infra qualifiers that make an otherwise generic title relevant.
_INFRA_QUALIFIER = (
    r"(linux|unix|windows|infrastructure|infra|cloud|network|storage|vmware|"
    r"devops|aws|azure|gcp|kubernetes|k8s|site|platform)"
)

# Maps internal role_type value to the patterns that identify it.
# Priority: first match wins — order matters.
ROLE_TYPE_MAP: dict[str, list[str]] = {
    "devops": [
        r"\bdevops\b",
        r"\bdev ops\b",
        r"\bdevsecops\b",
        r"\bgitops\b",
        r"\baiops\b",
        r"\bdataops\b",
        r"\brelease engineer",
        r"\bbuild engineer",
        r"\bbuild (and|&) release\b",
        r"\bci ?/ ?cd\b",
        r"\bcicd\b",
        r"\bdeveloper productivity\b",
        r"\bdeveloper experience\b",
        r"\bdevex\b",
        r"\bkubernetes (engineer|administrator|admin|specialist|architect)\b",
        r"\bk8s engineer\b",
        r"\bterraform engineer\b",
        r"\binfrastructure as code\b",
    ],
    "sre": [
        r"\bsre\b",
        r"\bsite reliability\b",
        r"\breliability engineer",
        r"\bplatform reliability\b",
        r"\bproduction engineer",
        r"\bdatabase reliability\b",
    ],
    "platform": [
        r"\bplatform engineer",
        r"\bplatform operations\b",
        r"\binternal developer platform\b",
    ],
    "cloud": [
        r"\bcloud engineer",
        r"\bcloud infrastructure\b",
        r"\bcloud operations\b",
        r"\bcloud ?ops\b",
        r"\bcloud platform\b",
        r"\bcloud administrator\b",
        r"\bcloud architect\b",
        r"\bcloud security engineer\b",
        r"\bcloud consultant\b",
        r"\b(aws|azure|gcp) (engineer|architect|administrator|consultant)\b",
        r"\bfinops\b",
    ],
    "infra": [
        r"\binfrastructure (engineer|engineering|architect|lead|specialist|manager|operations|automation)\b",
        r"\binfra (engineer|engineering|lead|architect)\b",
        r"\bit infrastructure\b",
        r"\bsystems? administrator\b",
        r"\bsysadmin\b",
        r"\b(linux|unix|windows) (administrator|admin|engineer)\b",
        rf"\b{_INFRA_QUALIFIER} systems? engineer\b",
        rf"\bsystems? engineer\b.*\b{_INFRA_QUALIFIER}\b",
        r"\bnetwork (engineer|operations|administrator|architect)\b",
        r"\bobservability\b",
        r"\bmonitoring engineer\b",
        r"\bstorage engineer\b",
        r"\bvirtuali[sz]ation engineer\b",
    ],
    "mlops": [
        r"\bmlops\b",
        r"\bllmops\b",
        r"\bml (infrastructure|platform|ops)\b",
        r"\bmachine learning (infrastructure|platform|operations)\b",
        r"\bai (platform|infrastructure)\b",
    ],
    "appsupport": [
        r"\bapplication support\b",
        r"\bapp support\b",
        r"\bproduction support\b",
        r"\bprod support\b",
        r"\bplatform support\b",
        r"\bops support\b",
        r"\boperations support\b",
    ],
    "techsupport": [
        r"\b(cloud|infrastructure|devops|kubernetes|linux|network|saas|platform) support\b",
        r"\btechnical support engineer\b",
        r"\bnoc (engineer|analyst|technician)\b",
        r"\bnetwork operations cent(er|re)\b",
        r"\b(l2|l3|tier 2|tier 3|level 2|level 3) support\b",
    ],
    "itops": [
        r"\bit operations\b",
        r"\bitops\b",
        r"\bdatabase administrator\b",
        r"\bdba\b",
    ],
}

# Entry-level IT helpdesk roles — classified as itops, toggled by
# INCLUDE_HELPDESK so they can be switched off without code changes.
HELPDESK_PATTERNS: list[str] = [
    r"\bservice desk\b",
    r"\bhelp ?desk\b",
    r"\bit support\b",
    r"\bdesktop support\b",
    r"\b(l1|tier 1|level 1) support\b",
]
if INCLUDE_HELPDESK:
    ROLE_TYPE_MAP["itops"] = ROLE_TYPE_MAP["itops"] + HELPDESK_PATTERNS

# Titles matching any of these are rejected even if a role keyword matched.
EXCLUDE_PATTERNS: list[str] = [
    # Product / data "platform" teams, not infrastructure platform teams
    r"\bdata platform\b",
    r"\b(front[\s-]?end|mobile|ios|android|web|payments?|commerce|growth|product|ads|marketing) platform\b",
    # Non-software engineering disciplines
    r"\b(mechanical|manufacturing|electrical|chemical|civil|automotive|aerospace|"
    r"plant|process|quality|hardware|hvac|maintenance|field service)\b",
    r"\bembedded\b",
    # Customer-facing / non-engineering roles that mention infra words
    r"\bcustomer (support|success|service)\b",
    r"\b(sales|account executive|marketing|recruit(er|ing)|talent)\b",
    # Broadcast / media production
    r"\b(video|tv|television|broadcast|media|music|film) production\b",
]

_ROLE_TYPE_COMPILED: dict[str, re.Pattern] = {
    role: re.compile("|".join(patterns), re.IGNORECASE)
    for role, patterns in ROLE_TYPE_MAP.items()
}
_ALL_PATTERNS: list[str] = [p for patterns in ROLE_TYPE_MAP.values() for p in patterns]
_KEYWORD_RE = re.compile("|".join(_ALL_PATTERNS), re.IGNORECASE)
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)


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
    r"\biv\b",
]
_ENTRY_PATTERNS: list[str] = [
    r"\bjunior\b",
    r"\bjr\.?\b",
    r"\bentry[\s\-]level\b",
    r"\bassociate\b",
    r"\bgraduate\b",
    r"\bintern\b",
]
_MID_PATTERNS: list[str] = [
    r"\bii\b",
    r"\bmid[\s\-]level\b",
    r"\bintermediate\b",
    r"\bmidlevel\b",
]


def _normalise(text: str) -> str:
    """Lower-case and collapse whitespace for consistent matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def is_excluded(title: str) -> bool:
    """
    Return True if the title matches a known false-positive pattern.

    Args:
        title: Job title string.
    """
    return bool(_EXCLUDE_RE.search(title or ""))


def matched_keyword(title: str) -> str | None:
    """
    Return the role keyword text that matched the title, for run diagnostics.

    Args:
        title: Job title string.

    Returns:
        Lower-cased matched text (e.g. 'site reliability'), or None if the
        title does not match or is excluded.
    """
    if not title or is_excluded(title):
        return None
    match = _KEYWORD_RE.search(title)
    return match.group(0).lower() if match else None


def matches_keyword(title: str, description: str = "") -> bool:
    """
    Return True if the job title contains a role keyword and is not excluded.

    Only the title is checked. Generic terms such as 'engineer', 'cloud',
    'platform' or 'support' alone do NOT match, and titles matching
    EXCLUDE_PATTERNS (data platform, mechanical, customer support, ...) are
    rejected.

    Args:
        title:       Job title string.
        description: Ignored; kept for call-site compatibility.

    Returns:
        True if the title is a relevant infra/ops role, False otherwise.
    """
    return matched_keyword(title) is not None


def detect_role_type(title: str) -> str:
    """
    Detect the primary role type from a job title.

    Checks role types in priority order:
      devops → sre → platform → cloud → infra → mlops →
      appsupport → techsupport → itops

    Args:
        title: Job title string.

    Returns:
        One of: 'devops', 'sre', 'platform', 'cloud', 'infra', 'mlops',
        'appsupport', 'techsupport', 'itops'. Returns 'other' if no pattern
        matches or the title is excluded — the orchestrator discards 'other'.
    """
    if not title or is_excluded(title):
        return "other"
    for role_type, pattern in _ROLE_TYPE_COMPILED.items():
        if pattern.search(title):
            return role_type
    return "other"


def detect_experience_level(title: str, description: str = "") -> str:
    """
    Detect experience level from the job title using keyword heuristics.

    Only the title is inspected: descriptions routinely say things like
    "lead projects" or "work with senior engineers", which caused most jobs
    to be mis-tagged as staff/senior.

    Args:
        title:       Job title string.
        description: Ignored; kept for call-site compatibility.

    Returns:
        One of: 'staff', 'senior', 'entry', 'mid'.
    """
    haystack = _normalise(title)

    if any(re.search(p, haystack) for p in _SENIOR_PATTERNS):
        return "staff"
    if any(re.search(p, haystack) for p in _SENIOR_LEVEL_PATTERNS):
        return "senior"
    if any(re.search(p, haystack) for p in _ENTRY_PATTERNS):
        return "entry"
    if any(re.search(p, haystack) for p in _MID_PATTERNS):
        return "mid"
    return "mid"

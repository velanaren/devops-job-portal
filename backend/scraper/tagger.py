# ---------------------------------------------------------------------------
# Step 1 — Source-based Remote Global
# ---------------------------------------------------------------------------

# These three sources are curated global-remote boards. Every job from them
# is inherently work-from-anywhere, regardless of the raw location string.
_SOURCE_REMOTE_GLOBAL: frozenset[str] = frozenset({"RemoteOK", "Remotive", "Jobicy"})

# ---------------------------------------------------------------------------
# Step 2 — Explicit worldwide keyword detection
# ---------------------------------------------------------------------------

# Only these phrases mean truly global/work-from-anywhere.
# "Remote" alone and "Fully Remote" alone do NOT qualify — on Greenhouse/Lever/Ashby
# those terms typically mean remote within US/EU, not accessible from India.
_REMOTE_GLOBAL_KEYWORDS: tuple[str, ...] = (
    "work from anywhere",
    "anywhere in the world",
    "worldwide",
    "no location restriction",
    "location independent",
    "wfa",
    "remote - worldwide",
    "remote - global",
    "remote - anywhere",
    "global - remote",
    "global remote",
    "remote worldwide",
    "remote global",
)

# ---------------------------------------------------------------------------
# Step 3 — India city checks
# ---------------------------------------------------------------------------

# Checked BEFORE the US false-positive guard so that e.g. "Pune, IN" correctly
# returns "Pune" rather than being swallowed by the Indiana/IN indicator.

# ---------------------------------------------------------------------------
# Step 4 — US false positive guard
# ---------------------------------------------------------------------------

_US_CITY_INDICATORS: tuple[str, ...] = (
    "united states", "usa", "u.s.a", "u.s.",
    ", ca", ", ny", ", tx", ", wa", ", ma",
    ", il", ", ga", ", fl", ", co", ", va",
    ", md", ", pa", ", nc", ", oh", ", mi",
    ", nj", ", az", ", mn", ", mo", ", tn",
    "indiana", "indianapolis",
    "california", "texas", "washington dc",
    "washington, d.c", "new york, ny",
    "new york, new york",
)

# ---------------------------------------------------------------------------
# Step 5 — Remote India
# ---------------------------------------------------------------------------

_INDIA_REMOTE_SIGNALS: tuple[str, ...] = (
    "remote", "wfh", "work from home",
    "pan india", "anywhere in india",
    "india remote", "remote india",
)

# ---------------------------------------------------------------------------
# Step 6 — Other India cities
# ---------------------------------------------------------------------------

_OTHER_INDIA_CITIES: tuple[str, ...] = (
    "kolkata", "calcutta", "ahmedabad",
    "jaipur", "kochi", "cochin",
    "coimbatore", "thiruvananthapuram",
    "trivandrum", "indore", "nagpur",
    "chandigarh", "lucknow", "bhopal",
    "surat", "vadodara", "baroda",
    "visakhapatnam", "vizag",
    "bhubaneswar", "patna", "ranchi",
    "mysuru", "mysore", "mangalore",
    "mangaluru", "thrissur", "madurai",
)


def _is_us_location(loc: str) -> bool:
    """Return True if the lowercased location string matches a US indicator."""
    return any(indicator in loc for indicator in _US_CITY_INDICATORS)


def tag_location(location_raw: str, source_name: str) -> str:
    """
    Derive a location tag from the raw location string and source name.

    Priority order (highest to lowest):
      1.  Remote Global  — source-based (RemoteOK / Remotive / Jobicy always)
      2.  Remote Global  — explicit worldwide keyword
      3.  Bengaluru / Chennai / Hyderabad / Pune / Mumbai / Delhi NCR
          (city checks run BEFORE the US guard so "Pune, IN" → Pune, not Global)
      4.  Global         — US false-positive detected → filter out
      5.  Remote India   — india + remote signal
      6.  Other India    — remaining India locations
      7.  Global         — fallback

    Args:
        location_raw: Raw location string as received from the source API.
        source_name:  Human-readable source name (e.g. 'RemoteOK', 'Greenhouse').

    Returns:
        One of: 'Remote Global', 'Remote India', 'Bengaluru', 'Chennai',
        'Hyderabad', 'Pune', 'Mumbai', 'Delhi NCR', 'Other India', 'Global'.
    """
    loc = location_raw.lower().strip() if location_raw else ""

    # ------------------------------------------------------------------
    # Step 1 — Source-based Remote Global.
    #
    # Curated global-remote boards: every job is work-from-anywhere.
    # Himalayas: empty location or "Worldwide" means truly global.
    # ------------------------------------------------------------------
    if source_name in _SOURCE_REMOTE_GLOBAL:
        return "Remote Global"

    if source_name == "Himalayas" and loc in ("worldwide", ""):
        return "Remote Global"

    # ------------------------------------------------------------------
    # Step 2 — Explicit worldwide keyword.
    #
    # "Remote" alone and "Fully Remote" alone are intentionally absent from
    # the keyword list — on ATS boards those mean US/EU remote, not India.
    # ------------------------------------------------------------------
    if any(kw in loc for kw in _REMOTE_GLOBAL_KEYWORDS):
        return "Remote Global"

    # ------------------------------------------------------------------
    # Step 3 — Specific India city checks.
    #
    # Run BEFORE the US guard so that compound strings like "Pune, IN" or
    # "Mumbai, MH" are caught here rather than misclassified as US.
    # ------------------------------------------------------------------
    if "bengaluru" in loc or "bangalore" in loc:
        return "Bengaluru"

    if "chennai" in loc:
        return "Chennai"

    if "hyderabad" in loc:
        return "Hyderabad"

    if "pune" in loc:
        return "Pune"

    if "mumbai" in loc or "bombay" in loc:
        return "Mumbai"

    if any(city in loc for city in ("delhi", "noida", "gurugram", "gurgaon", "faridabad")):
        return "Delhi NCR"

    # ------------------------------------------------------------------
    # Step 4 — US false-positive guard.
    #
    # Must come AFTER Step 3 so specific India cities already returned.
    # Catches "Remote - United States", "Indianapolis, IN", state suffixes, etc.
    # ------------------------------------------------------------------
    if _is_us_location(loc):
        return "Global"

    # ------------------------------------------------------------------
    # Step 5 — Remote India.
    #
    # Requires an India indicator AND a remote-work signal.
    # loc.endswith(", in") catches "Pune, IN"-style strings not caught in
    # Step 3 (though those should already be handled above).
    # ------------------------------------------------------------------
    has_india = "india" in loc or loc.endswith(", in")
    has_remote = any(signal in loc for signal in _INDIA_REMOTE_SIGNALS)

    if has_india and has_remote:
        return "Remote India"

    # ------------------------------------------------------------------
    # Step 6 — Other India.
    #
    # Bare "india" keyword or an Indian city not in the specific city list.
    # ------------------------------------------------------------------
    if "india" in loc or any(city in loc for city in _OTHER_INDIA_CITIES):
        return "Other India"

    # ------------------------------------------------------------------
    # Step 7 — Global fallback.
    #
    # International locations not matching any India pattern.
    # These are filtered out by the scraper (CHANGE 2) before DB write.
    # ------------------------------------------------------------------
    return "Global"

import re

# ---------------------------------------------------------------------------
# Step 1 — Source-based defaults
# ---------------------------------------------------------------------------

# Sources where "Worldwide" with no locationRestrictions means truly global.
_HIMALAYAS_WORLDWIDE: frozenset[str] = frozenset({"Himalayas"})

# ---------------------------------------------------------------------------
# Step 2 — Remote Global keyword detection
# ---------------------------------------------------------------------------

_REMOTE_GLOBAL_KEYWORDS: tuple[str, ...] = (
    "anywhere",
    "worldwide",
    "work from anywhere",
    "no location",
    "fully remote",
    "global remote",
    "remote - worldwide",
    "wfa",
    "location independent",
)

# Country/region names that indicate a geographic restriction.
# If any of these appear alongside a Remote Global keyword, the job is NOT
# Remote Global — it is limited to a specific region.
_COUNTRY_RESTRICTION_RE = re.compile(
    r"\b("
    r"usa?|united states|us only"
    r"|canada|uk|united kingdom"
    r"|europe|emea|latam"
    r"|australia|new zealand"
    r"|germany|france|netherlands|sweden|denmark|norway|finland"
    r"|spain|italy|portugal|poland"
    r"|brazil|colombia|argentina|mexico"
    r"|singapore|japan|china|korea"
    r"|india"
    r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Step 3 — Remote India indicators
# ---------------------------------------------------------------------------

_REMOTE_INDIA_INDICATORS: tuple[str, ...] = (
    "remote",
    "work from home",
    "wfh",
    "pan india",
    "anywhere in india",
)

# Cities that should NOT be tagged Remote India — they get their own category.
_INDIA_CITY_EXCEPTIONS: tuple[str, ...] = (
    "bengaluru",
    "bangalore",
    "chennai",
    "hyderabad",
)

# ---------------------------------------------------------------------------
# Step 7 — Other India city list
# ---------------------------------------------------------------------------

_OTHER_INDIA_CITIES: tuple[str, ...] = (
    "pune",
    "mumbai",
    "delhi",
    "noida",
    "gurugram",
    "gurgaon",
    "kolkata",
    "ahmedabad",
    "jaipur",
    "kochi",
    "coimbatore",
    "thiruvananthapuram",
    "trivandrum",
    "indore",
    "nagpur",
    "chandigarh",
    "lucknow",
    "bhopal",
    "surat",
    "vadodara",
)


def tag_location(location_raw: str, source_name: str) -> str:
    """
    Derive a 7-category location tag from the raw location string and source name.

    Priority order (highest to lowest):
      1. Remote Global  — truly work from anywhere worldwide, no country restriction
      2. Remote India   — work remotely from within India
      3. Bengaluru      — physical presence in Bengaluru / Bangalore
      4. Chennai        — physical presence in Chennai
      5. Hyderabad      — physical presence in Hyderabad
      6. Other India    — other Indian cities (Pune, Mumbai, Delhi, etc.)
      7. Global         — international locations not matching the above

    Args:
        location_raw: Raw location string as received from the source API.
        source_name:  Human-readable source name (e.g. 'RemoteOK', 'Greenhouse').

    Returns:
        One of: 'Remote Global', 'Remote India', 'Bengaluru', 'Chennai',
        'Hyderabad', 'Other India', 'Global'.
    """
    loc = location_raw.lower().strip() if location_raw else ""

    # ------------------------------------------------------------------
    # Step 1 — Source-based defaults before text matching.
    #
    # Himalayas uses locationRestrictions=[] to mean truly worldwide remote.
    # When that field is empty the API returns "Worldwide".
    # ------------------------------------------------------------------
    if source_name in _HIMALAYAS_WORLDWIDE and location_raw == "Worldwide":
        return "Remote Global"

    # ------------------------------------------------------------------
    # Step 2 — Remote Global via explicit keywords.
    #
    # Matches only when a Remote Global keyword is present AND no country
    # name / region restriction is also present in the string.
    # ------------------------------------------------------------------
    if any(kw in loc for kw in _REMOTE_GLOBAL_KEYWORDS):
        if not _COUNTRY_RESTRICTION_RE.search(loc):
            return "Remote Global"

    # ------------------------------------------------------------------
    # Step 3 — Remote India.
    #
    # Requires "india" + a remote-work indicator, but must NOT mention a
    # specific Indian city (those are handled in Steps 4–6 below).
    # ------------------------------------------------------------------
    if "india" in loc and any(ind in loc for ind in _REMOTE_INDIA_INDICATORS):
        if not any(city in loc for city in _INDIA_CITY_EXCEPTIONS):
            return "Remote India"

    # ------------------------------------------------------------------
    # Step 4 — Bengaluru.
    # ------------------------------------------------------------------
    if "bengaluru" in loc or "bangalore" in loc:
        return "Bengaluru"

    # ------------------------------------------------------------------
    # Step 5 — Chennai.
    # ------------------------------------------------------------------
    if "chennai" in loc:
        return "Chennai"

    # ------------------------------------------------------------------
    # Step 6 — Hyderabad.
    # ------------------------------------------------------------------
    if "hyderabad" in loc:
        return "Hyderabad"

    # ------------------------------------------------------------------
    # Step 7 — Other India.
    #
    # Catches any remaining Indian locations: bare "india" keyword or a
    # recognised Indian city not covered by Steps 4–6.
    # ------------------------------------------------------------------
    if "india" in loc or any(city in loc for city in _OTHER_INDIA_CITIES):
        return "Other India"

    # ------------------------------------------------------------------
    # Step 8 — Global fallback.
    #
    # International locations that are not India and not truly remote.
    # ------------------------------------------------------------------
    return "Global"

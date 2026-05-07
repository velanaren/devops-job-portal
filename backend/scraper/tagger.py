import re

# Sources that are remote-only job boards — default to Remote Global unless
# the location field explicitly restricts to a specific country.
_REMOTE_ONLY_SOURCES: frozenset[str] = frozenset(
    {"RemoteOK", "Remotive", "Jobicy"}
)

_COUNTRY_RESTRICTION_PATTERN = re.compile(
    r"\b(usa?|united states|us only|canada|uk|united kingdom|europe|australia|germany|france)\b",
    re.IGNORECASE,
)


def tag_location(location_raw: str, source_name: str) -> str:
    """
    Derive a location priority tag from the raw location string and source name.

    Priority order:
      1. Chennai
      2. Bengaluru
      3. Remote India  (india + remote)
      4. Remote Global (remote-only source OR generic remote keywords)
      5. Other

    Args:
        location_raw: Raw location string as received from the source API.
        source_name:  Human-readable source name (e.g. 'RemoteOK', 'Greenhouse').

    Returns:
        One of: 'Remote Global', 'Remote India', 'Chennai', 'Bengaluru', 'Other'.
    """
    loc = location_raw.lower().strip() if location_raw else ""

    # City matches take highest priority regardless of source.
    if "chennai" in loc:
        return "Chennai"

    if "bengaluru" in loc or "bangalore" in loc:
        return "Bengaluru"

    # Remote India: location mentions both india and remote.
    if "india" in loc and "remote" in loc:
        return "Remote India"

    # Remote Global via generic location keywords.
    _REMOTE_GLOBAL_KEYWORDS = (
        "anywhere",
        "worldwide",
        "global",
        "work from anywhere",
        "wfa",
        "fully remote",
    )
    if any(kw in loc for kw in _REMOTE_GLOBAL_KEYWORDS):
        return "Remote Global"

    if "remote" in loc and not _COUNTRY_RESTRICTION_PATTERN.search(loc):
        return "Remote Global"

    # Remote-only source boards default to Remote Global unless a country
    # restriction was detected above.
    if source_name in _REMOTE_ONLY_SOURCES:
        if not _COUNTRY_RESTRICTION_PATTERN.search(loc):
            return "Remote Global"

    return "Other"

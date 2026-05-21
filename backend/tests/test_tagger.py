import pytest
from scraper.tagger import tag_location


# ---------------------------------------------------------------------------
# Remote Global — keyword-based
# ---------------------------------------------------------------------------

class TestRemoteGlobalKeywords:
    def test_anywhere(self):
        assert tag_location("Anywhere", "Greenhouse") == "Remote Global"

    def test_worldwide(self):
        assert tag_location("Worldwide", "Greenhouse") == "Remote Global"

    def test_work_from_anywhere(self):
        assert tag_location("Work From Anywhere", "Ashby") == "Remote Global"

    def test_no_location(self):
        assert tag_location("No Location", "Lever") == "Remote Global"

    def test_fully_remote(self):
        assert tag_location("Fully Remote", "Greenhouse") == "Remote Global"

    def test_global_remote(self):
        assert tag_location("Global Remote", "Lever") == "Remote Global"

    def test_remote_worldwide(self):
        assert tag_location("Remote - Worldwide", "Greenhouse") == "Remote Global"

    def test_wfa(self):
        assert tag_location("WFA", "Ashby") == "Remote Global"

    def test_location_independent(self):
        assert tag_location("Location Independent", "Lever") == "Remote Global"

    def test_keywords_case_insensitive(self):
        assert tag_location("FULLY REMOTE", "Greenhouse") == "Remote Global"

    def test_worldwide_uppercase(self):
        assert tag_location("WORLDWIDE", "Lever") == "Remote Global"


# ---------------------------------------------------------------------------
# Remote Global — exclusions (country-restricted "remote" must NOT be Remote Global)
# ---------------------------------------------------------------------------

class TestRemoteGlobalExclusions:
    def test_remote_us_only(self):
        # "remote - us only" does not contain a Remote Global keyword → Global
        assert tag_location("Remote - US only", "Greenhouse") == "Global"

    def test_remote_usa(self):
        assert tag_location("Remote - USA", "Greenhouse") == "Global"

    def test_remote_united_states(self):
        assert tag_location("Remote - United States", "Lever") == "Global"

    def test_remote_europe(self):
        assert tag_location("Remote - Europe", "Ashby") == "Global"

    def test_remote_uk(self):
        assert tag_location("Remote - UK", "Greenhouse") == "Global"

    def test_remote_canada(self):
        assert tag_location("Remote - Canada", "Lever") == "Global"

    def test_remote_australia(self):
        assert tag_location("Remote - Australia", "Greenhouse") == "Global"

    def test_remote_germany(self):
        assert tag_location("Remote - Germany", "Ashby") == "Global"

    def test_remote_brazil(self):
        assert tag_location("Remote - Brazil", "Greenhouse") == "Global"

    def test_remote_latam(self):
        assert tag_location("Remote - LATAM", "Lever") == "Global"

    def test_remote_emea(self):
        assert tag_location("Remote - EMEA", "Greenhouse") == "Global"

    def test_fully_remote_with_country(self):
        # "fully remote" keyword present but "united states" restricts it
        assert tag_location("Fully Remote, United States", "Greenhouse") == "Global"

    def test_anywhere_in_india_is_not_remote_global(self):
        # "anywhere" is a keyword but "india" is a country restriction → falls to Remote India
        assert tag_location("Anywhere in India", "Greenhouse") == "Remote India"

    def test_plain_remote_is_not_remote_global(self):
        # bare "remote" is not in the keyword list
        assert tag_location("Remote", "Greenhouse") == "Global"

    def test_plain_global_is_not_remote_global(self):
        # "global" alone is not a keyword; "global remote" is
        assert tag_location("Global", "Lever") == "Global"


# ---------------------------------------------------------------------------
# Remote Global — Himalayas source-based default (Step 1)
# ---------------------------------------------------------------------------

class TestRemoteGlobalHimalayas:
    def test_himalayas_worldwide(self):
        assert tag_location("Worldwide", "Himalayas") == "Remote Global"

    def test_himalayas_non_worldwide_falls_through(self):
        # "Remote" from Himalayas does not trigger Step 1; no keyword → Global
        assert tag_location("Remote", "Himalayas") == "Global"

    def test_non_himalayas_worldwide_uses_keyword(self):
        # "Worldwide" still matches the Step 2 keyword for any source
        assert tag_location("Worldwide", "Greenhouse") == "Remote Global"


# ---------------------------------------------------------------------------
# Remote India
# ---------------------------------------------------------------------------

class TestRemoteIndia:
    def test_india_remote(self):
        assert tag_location("India, Remote", "Greenhouse") == "Remote India"

    def test_remote_india(self):
        assert tag_location("Remote - India", "Lever") == "Remote India"

    def test_india_remote_lowercase(self):
        assert tag_location("india remote", "Ashby") == "Remote India"

    def test_work_from_home_india(self):
        assert tag_location("Work from home, India", "Greenhouse") == "Remote India"

    def test_wfh_india(self):
        assert tag_location("WFH, India", "Lever") == "Remote India"

    def test_pan_india(self):
        assert tag_location("Pan India", "Greenhouse") == "Remote India"

    def test_anywhere_in_india(self):
        assert tag_location("Anywhere in India", "Greenhouse") == "Remote India"

    def test_india_without_remote_is_other_india(self):
        # "india" alone has no remote indicator → falls to Other India (Step 7)
        assert tag_location("India", "Greenhouse") == "Other India"

    def test_bengaluru_india_remote_is_bengaluru(self):
        # City exception in Step 3 guard — Bengaluru wins
        assert tag_location("Bengaluru, India (Remote)", "Greenhouse") == "Bengaluru"

    def test_chennai_india_remote_is_chennai(self):
        assert tag_location("Chennai, India (Remote)", "Lever") == "Chennai"

    def test_hyderabad_india_remote_is_hyderabad(self):
        assert tag_location("Hyderabad, India (Remote)", "Ashby") == "Hyderabad"


# ---------------------------------------------------------------------------
# Bengaluru
# ---------------------------------------------------------------------------

class TestBengaluru:
    def test_bengaluru_exact(self):
        assert tag_location("Bengaluru", "Greenhouse") == "Bengaluru"

    def test_bangalore_variant(self):
        assert tag_location("Bangalore", "Lever") == "Bengaluru"

    def test_bengaluru_with_state(self):
        assert tag_location("Bengaluru, Karnataka, India", "Ashby") == "Bengaluru"

    def test_bangalore_case_insensitive(self):
        assert tag_location("BANGALORE", "Greenhouse") == "Bengaluru"

    def test_bengaluru_remote_no_india(self):
        # No "india" in string → Step 3 skipped → Step 4 → Bengaluru
        assert tag_location("Bengaluru (Remote)", "Greenhouse") == "Bengaluru"


# ---------------------------------------------------------------------------
# Chennai
# ---------------------------------------------------------------------------

class TestChennai:
    def test_chennai_exact(self):
        assert tag_location("Chennai", "Greenhouse") == "Chennai"

    def test_chennai_with_state(self):
        assert tag_location("Chennai, Tamil Nadu, India", "Lever") == "Chennai"

    def test_chennai_case_insensitive(self):
        assert tag_location("CHENNAI", "Ashby") == "Chennai"

    def test_chennai_remote_no_india(self):
        # No "india" → Step 3 skipped → Step 5 → Chennai
        assert tag_location("Chennai (Remote)", "Greenhouse") == "Chennai"


# ---------------------------------------------------------------------------
# Hyderabad (new category)
# ---------------------------------------------------------------------------

class TestHyderabad:
    def test_hyderabad_exact(self):
        assert tag_location("Hyderabad", "Greenhouse") == "Hyderabad"

    def test_hyderabad_with_state(self):
        assert tag_location("Hyderabad, Telangana, India", "Lever") == "Hyderabad"

    def test_hyderabad_case_insensitive(self):
        assert tag_location("HYDERABAD", "Ashby") == "Hyderabad"

    def test_hyderabad_with_india_no_remote(self):
        # "india" + no remote indicator → Step 3 skipped → Step 6 → Hyderabad
        assert tag_location("Hyderabad, India", "Greenhouse") == "Hyderabad"


# ---------------------------------------------------------------------------
# Other India
# ---------------------------------------------------------------------------

class TestOtherIndia:
    def test_mumbai(self):
        assert tag_location("Mumbai, India", "Greenhouse") == "Other India"

    def test_pune(self):
        assert tag_location("Pune", "Lever") == "Other India"

    def test_delhi(self):
        assert tag_location("Delhi, India", "Ashby") == "Other India"

    def test_noida(self):
        assert tag_location("Noida", "Greenhouse") == "Other India"

    def test_gurugram(self):
        assert tag_location("Gurugram", "Lever") == "Other India"

    def test_gurgaon(self):
        assert tag_location("Gurgaon", "Greenhouse") == "Other India"

    def test_kolkata(self):
        assert tag_location("Kolkata", "Ashby") == "Other India"

    def test_india_bare(self):
        # "india" with no remote indicator → Other India
        assert tag_location("India", "Greenhouse") == "Other India"

    def test_mumbai_no_india_keyword(self):
        # "mumbai" alone triggers Other India via city list
        assert tag_location("Mumbai", "Lever") == "Other India"

    def test_kochi(self):
        assert tag_location("Kochi, Kerala, India", "Greenhouse") == "Other India"


# ---------------------------------------------------------------------------
# Global fallback
# ---------------------------------------------------------------------------

class TestGlobal:
    def test_london(self):
        assert tag_location("London, UK", "Greenhouse") == "Global"

    def test_new_york(self):
        assert tag_location("New York, USA", "Lever") == "Global"

    def test_singapore(self):
        assert tag_location("Singapore", "Ashby") == "Global"

    def test_empty_greenhouse(self):
        assert tag_location("", "Greenhouse") == "Global"

    def test_empty_remoteok(self):
        # RemoteOK no longer has a source-based Remote Global default
        assert tag_location("", "RemoteOK") == "Global"

    def test_empty_remotive(self):
        assert tag_location("", "Remotive") == "Global"

    def test_empty_jobicy(self):
        assert tag_location("", "Jobicy") == "Global"

    def test_plain_remote_is_global(self):
        # "remote" alone is not in the keyword list
        assert tag_location("Remote", "Greenhouse") == "Global"

    def test_plain_global_string_is_global(self):
        # "global" alone is not a keyword; only "global remote" is
        assert tag_location("Global", "Lever") == "Global"

    def test_us_restricted_remote(self):
        assert tag_location("Remote - US only", "Greenhouse") == "Global"

    def test_berlin(self):
        assert tag_location("Berlin, Germany", "Ashby") == "Global"

    def test_toronto(self):
        assert tag_location("Toronto, Canada", "Greenhouse") == "Global"

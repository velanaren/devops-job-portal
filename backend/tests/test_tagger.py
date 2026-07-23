import pytest
from scraper.tagger import tag_location


# ---------------------------------------------------------------------------
# Remote Global — source-based overrides (Step 1)
# ---------------------------------------------------------------------------

class TestRemoteGlobalSourceBased:
    def test_remoteok_empty(self):
        assert tag_location("", "RemoteOK") == "Remote Global"

    def test_remoteok_with_location(self):
        # Source override fires regardless of location string
        assert tag_location("Worldwide", "RemoteOK") == "Remote Global"

    def test_remotive_empty(self):
        assert tag_location("", "Remotive") == "Remote Global"

    def test_remotive_with_location(self):
        assert tag_location("Worldwide", "Remotive") == "Remote Global"

    def test_jobicy_empty(self):
        assert tag_location("", "Jobicy") == "Remote Global"

    def test_jobicy_with_location(self):
        assert tag_location("Worldwide", "Jobicy") == "Remote Global"

    def test_himalayas_worldwide(self):
        assert tag_location("Worldwide", "Himalayas") == "Remote Global"

    def test_himalayas_empty(self):
        assert tag_location("", "Himalayas") == "Remote Global"

    def test_himalayas_non_worldwide_falls_through(self):
        # Only "Worldwide" and "" trigger the Himalayas source override
        assert tag_location("Remote", "Himalayas") == "Global"

    def test_non_himalayas_worldwide_uses_keyword(self):
        # "Worldwide" still matches the Step 2 keyword for any source
        assert tag_location("Worldwide", "Greenhouse") == "Remote Global"


# ---------------------------------------------------------------------------
# Remote Global — keyword-based (Step 2)
# ---------------------------------------------------------------------------

class TestRemoteGlobalKeywords:
    def test_worldwide(self):
        assert tag_location("Worldwide", "Greenhouse") == "Remote Global"

    def test_work_from_anywhere(self):
        assert tag_location("Work From Anywhere", "Ashby") == "Remote Global"

    def test_global_remote(self):
        assert tag_location("Global Remote", "Lever") == "Remote Global"

    def test_remote_worldwide(self):
        assert tag_location("Remote - Worldwide", "Greenhouse") == "Remote Global"

    def test_remote_global(self):
        assert tag_location("Remote - Global", "Lever") == "Remote Global"

    def test_wfa(self):
        assert tag_location("WFA", "Ashby") == "Remote Global"

    def test_location_independent(self):
        assert tag_location("Location Independent", "Lever") == "Remote Global"

    def test_remote_anywhere(self):
        assert tag_location("Remote - Anywhere", "Greenhouse") == "Remote Global"

    def test_worldwide_uppercase(self):
        assert tag_location("WORLDWIDE", "Lever") == "Remote Global"

    def test_work_from_anywhere_in_the_world(self):
        assert tag_location("Anywhere in the World", "Greenhouse") == "Remote Global"

    # "Remote" alone and "Fully Remote" alone are NOT Remote Global on ATS sources
    def test_plain_remote_is_not_remote_global(self):
        assert tag_location("Remote", "Greenhouse") == "Global"

    def test_fully_remote_is_not_remote_global(self):
        # "Fully Remote" on Greenhouse/Lever means US/EU remote — not India-accessible
        assert tag_location("Fully Remote", "Greenhouse") == "Global"

    def test_fully_remote_uppercase_is_not_remote_global(self):
        assert tag_location("FULLY REMOTE", "Greenhouse") == "Global"

    def test_plain_global_is_not_remote_global(self):
        assert tag_location("Global", "Lever") == "Global"


# ---------------------------------------------------------------------------
# Remote Global — exclusions / US false positives (Step 4)
# ---------------------------------------------------------------------------

class TestRemoteGlobalExclusions:
    def test_remote_us_only(self):
        assert tag_location("Remote - US only", "Greenhouse") == "Global"

    def test_remote_usa(self):
        assert tag_location("Remote - USA", "Greenhouse") == "Global"

    def test_remote_united_states(self):
        assert tag_location("Remote - United States", "Lever") == "Global"

    def test_remote_europe(self):
        # "europe" is not a US indicator — falls to Global fallback
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

    def test_indianapolis(self):
        assert tag_location("Indianapolis, IN", "Greenhouse") == "Global"

    def test_indianapolis_full(self):
        assert tag_location("Indianapolis, Indiana, United States", "Greenhouse") == "Global"

    def test_united_states(self):
        assert tag_location("United States", "Greenhouse") == "Global"

    def test_anywhere_in_india_is_not_remote_global(self):
        # "anywhere in india" is an India remote signal → Remote India
        assert tag_location("Anywhere in India", "Greenhouse") == "Remote India"


# ---------------------------------------------------------------------------
# City checks come BEFORE US guard (Step 3 before Step 4)
# ---------------------------------------------------------------------------

class TestCityBeforeUSGuard:
    def test_pune_in_suffix(self):
        # "IN" suffix would trigger US guard for indiana — but "pune" is caught first
        assert tag_location("Pune, IN", "Greenhouse") == "Pune"

    def test_pune_maharashtra(self):
        assert tag_location("Pune, Maharashtra, India", "Greenhouse") == "Pune"

    def test_mumbai_mh(self):
        assert tag_location("Mumbai, MH", "Greenhouse") == "Mumbai"

    def test_mumbai_india(self):
        assert tag_location("Mumbai, India", "Greenhouse") == "Mumbai"

    def test_bombay(self):
        assert tag_location("Bombay", "Greenhouse") == "Mumbai"

    def test_mumbai_bare(self):
        assert tag_location("Mumbai", "Lever") == "Mumbai"


# ---------------------------------------------------------------------------
# Remote India
# ---------------------------------------------------------------------------

class TestRemoteIndia:
    def test_india_remote(self):
        assert tag_location("India, Remote", "Greenhouse") == "Remote India"

    def test_remote_india(self):
        assert tag_location("Remote - India", "Lever") == "Remote India"

    def test_india_remote_keyword(self):
        assert tag_location("India Remote", "Greenhouse") == "Remote India"

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
        assert tag_location("India", "Greenhouse") == "Other India"

    def test_bengaluru_india_remote_is_bengaluru(self):
        # City check (Step 3) fires before Remote India (Step 5)
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
        assert tag_location("Bengaluru (Remote)", "Greenhouse") == "Bengaluru"

    def test_bengaluru_india(self):
        assert tag_location("Bengaluru, India", "Greenhouse") == "Bengaluru"


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
        assert tag_location("Chennai (Remote)", "Greenhouse") == "Chennai"

    def test_chennai_india(self):
        assert tag_location("Chennai, India", "Greenhouse") == "Chennai"


# ---------------------------------------------------------------------------
# Hyderabad
# ---------------------------------------------------------------------------

class TestHyderabad:
    def test_hyderabad_exact(self):
        assert tag_location("Hyderabad", "Greenhouse") == "Hyderabad"

    def test_hyderabad_with_state(self):
        assert tag_location("Hyderabad, Telangana, India", "Lever") == "Hyderabad"

    def test_hyderabad_case_insensitive(self):
        assert tag_location("HYDERABAD", "Ashby") == "Hyderabad"

    def test_hyderabad_with_india_no_remote(self):
        assert tag_location("Hyderabad, India", "Greenhouse") == "Hyderabad"


# ---------------------------------------------------------------------------
# Pune (new dedicated tag)
# ---------------------------------------------------------------------------

class TestPune:
    def test_pune_exact(self):
        assert tag_location("Pune", "Lever") == "Pune"

    def test_pune_with_state(self):
        assert tag_location("Pune, Maharashtra, India", "Greenhouse") == "Pune"

    def test_pune_case_insensitive(self):
        assert tag_location("PUNE", "Ashby") == "Pune"

    def test_pune_in_suffix(self):
        assert tag_location("Pune, IN", "Greenhouse") == "Pune"


# ---------------------------------------------------------------------------
# Mumbai (new dedicated tag)
# ---------------------------------------------------------------------------

class TestMumbai:
    def test_mumbai_exact(self):
        assert tag_location("Mumbai", "Lever") == "Mumbai"

    def test_mumbai_india(self):
        assert tag_location("Mumbai, India", "Greenhouse") == "Mumbai"

    def test_bombay(self):
        assert tag_location("Bombay", "Ashby") == "Mumbai"

    def test_mumbai_mh(self):
        assert tag_location("Mumbai, MH", "Greenhouse") == "Mumbai"


# ---------------------------------------------------------------------------
# Delhi NCR (new dedicated tag)
# ---------------------------------------------------------------------------

class TestDelhiNCR:
    def test_delhi(self):
        assert tag_location("Delhi", "Greenhouse") == "Delhi NCR"

    def test_new_delhi(self):
        assert tag_location("New Delhi, Delhi, India", "Greenhouse") == "Delhi NCR"

    def test_noida(self):
        assert tag_location("Noida", "Greenhouse") == "Delhi NCR"

    def test_noida_up(self):
        assert tag_location("Noida, Uttar Pradesh", "Greenhouse") == "Delhi NCR"

    def test_gurugram(self):
        assert tag_location("Gurugram", "Lever") == "Delhi NCR"

    def test_gurugram_india(self):
        assert tag_location("Gurugram, India", "Greenhouse") == "Delhi NCR"

    def test_gurgaon(self):
        assert tag_location("Gurgaon", "Greenhouse") == "Delhi NCR"

    def test_gurgaon_haryana(self):
        assert tag_location("Gurgaon, Haryana", "Greenhouse") == "Delhi NCR"

    def test_faridabad(self):
        assert tag_location("Faridabad, Haryana", "Greenhouse") == "Delhi NCR"


# ---------------------------------------------------------------------------
# Other India
# ---------------------------------------------------------------------------

class TestOtherIndia:
    def test_kolkata(self):
        assert tag_location("Kolkata", "Ashby") == "Other India"

    def test_kolkata_india(self):
        assert tag_location("Kolkata, India", "Greenhouse") == "Other India"

    def test_kochi_india(self):
        assert tag_location("Kochi, India", "Greenhouse") == "Other India"

    def test_india_bare(self):
        assert tag_location("India", "Greenhouse") == "Other India"

    def test_ahmedabad(self):
        assert tag_location("Ahmedabad", "Lever") == "Other India"

    def test_jaipur(self):
        assert tag_location("Jaipur, Rajasthan, India", "Greenhouse") == "Other India"


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

    def test_brazil(self):
        assert tag_location("Brazil", "Greenhouse") == "Global"

    def test_empty_greenhouse(self):
        assert tag_location("", "Greenhouse") == "Global"

    def test_plain_remote_is_global(self):
        assert tag_location("Remote", "Greenhouse") == "Global"

    def test_plain_remote_lever(self):
        assert tag_location("Remote", "Lever") == "Global"

    def test_fully_remote_is_global(self):
        assert tag_location("Fully Remote", "Greenhouse") == "Global"

    def test_plain_global_string_is_global(self):
        assert tag_location("Global", "Lever") == "Global"

    def test_berlin(self):
        assert tag_location("Berlin, Germany", "Ashby") == "Global"

    def test_toronto(self):
        assert tag_location("Toronto, Canada", "Greenhouse") == "Global"

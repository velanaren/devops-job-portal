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

    def test_global(self):
        assert tag_location("Global", "Lever") == "Remote Global"

    def test_work_from_anywhere(self):
        assert tag_location("Work From Anywhere", "Ashby") == "Remote Global"

    def test_fully_remote(self):
        assert tag_location("Fully Remote", "Greenhouse") == "Remote Global"

    def test_remote_no_country(self):
        assert tag_location("Remote", "Greenhouse") == "Remote Global"

    def test_remote_case_insensitive(self):
        assert tag_location("REMOTE", "Greenhouse") == "Remote Global"


# ---------------------------------------------------------------------------
# Remote Global — source-based (remote-only boards)
# ---------------------------------------------------------------------------

class TestRemoteGlobalSource:
    def test_remoteok_empty_location(self):
        assert tag_location("", "RemoteOK") == "Remote Global"

    def test_remoteok_generic_location(self):
        assert tag_location("remote", "RemoteOK") == "Remote Global"

    def test_remotive_empty_location(self):
        assert tag_location("", "Remotive") == "Remote Global"

    def test_jobicy_empty_location(self):
        assert tag_location("", "Jobicy") == "Remote Global"

    def test_remoteok_country_restricted(self):
        # RemoteOK job restricted to USA should not be Remote Global
        assert tag_location("USA only", "RemoteOK") == "Other"

    def test_remotive_uk_restriction(self):
        assert tag_location("UK", "Remotive") == "Other"


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

    def test_india_without_remote_is_other(self):
        assert tag_location("India", "Greenhouse") == "Other"


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

    def test_chennai_takes_priority_over_india_remote(self):
        # Chennai + remote in string — Chennai wins
        assert tag_location("Chennai (Remote)", "Greenhouse") == "Chennai"


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


# ---------------------------------------------------------------------------
# Other fallback
# ---------------------------------------------------------------------------

class TestOther:
    def test_london(self):
        assert tag_location("London, UK", "Greenhouse") == "Other"

    def test_new_york(self):
        assert tag_location("New York, USA", "Lever") == "Other"

    def test_mumbai(self):
        assert tag_location("Mumbai, India", "Greenhouse") == "Other"

    def test_empty_non_remote_source(self):
        assert tag_location("", "Greenhouse") == "Other"

    def test_onsite_hyderabad(self):
        assert tag_location("Hyderabad, India", "Ashby") == "Other"

    def test_remote_with_us_restriction(self):
        assert tag_location("Remote - US only", "Greenhouse") == "Other"

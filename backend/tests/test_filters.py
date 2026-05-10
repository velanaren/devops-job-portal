import pytest
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword


# ---------------------------------------------------------------------------
# matches_keyword
# ---------------------------------------------------------------------------

class TestMatchesKeyword:
    def test_matches_devops_in_title(self):
        assert matches_keyword("Senior DevOps Engineer") is True

    def test_matches_sre_in_title(self):
        assert matches_keyword("Site Reliability Engineer") is True

    def test_matches_keyword_in_description_only(self):
        assert matches_keyword("Software Engineer", "looking for a platform engineer") is True

    def test_matches_case_insensitive(self):
        assert matches_keyword("CLOUD ENGINEER") is True

    def test_matches_partial_phrase(self):
        assert matches_keyword("L2 Support Analyst") is True

    def test_no_match_unrelated_title(self):
        assert matches_keyword("Frontend React Developer") is False

    def test_no_match_empty_inputs(self):
        assert matches_keyword("", "") is False

    def test_matches_devsecops(self):
        assert matches_keyword("DevSecOps Lead") is True

    def test_matches_infra_engineer(self):
        assert matches_keyword("Infrastructure Engineer III") is True

    def test_matches_release_engineer(self):
        assert matches_keyword("Release Engineer") is True


# ---------------------------------------------------------------------------
# detect_role_type
# ---------------------------------------------------------------------------

class TestDetectRoleType:
    def test_devops(self):
        assert detect_role_type("DevOps Engineer") == "devops"

    def test_devops_devsecops(self):
        assert detect_role_type("DevSecOps Engineer") == "devops"

    def test_sre(self):
        assert detect_role_type("Senior SRE") == "sre"

    def test_sre_full_name(self):
        assert detect_role_type("Site Reliability Engineer") == "sre"

    def test_platform(self):
        assert detect_role_type("Platform Engineer") == "platform"

    def test_platform_engineering(self):
        assert detect_role_type("Head of Platform Engineering") == "platform"

    def test_cloud(self):
        assert detect_role_type("Cloud Engineer") == "cloud"

    def test_cloud_infrastructure(self):
        assert detect_role_type("Cloud Infrastructure Lead") == "cloud"

    def test_appsupport(self):
        assert detect_role_type("Application Support Analyst") == "appsupport"

    def test_appsupport_short(self):
        assert detect_role_type("App Support Engineer") == "appsupport"

    def test_techsupport(self):
        assert detect_role_type("Technical Support Engineer") == "techsupport"

    def test_techsupport_l1(self):
        assert detect_role_type("L1 Support Specialist") == "techsupport"

    def test_techsupport_l2(self):
        assert detect_role_type("L2 Support Engineer") == "techsupport"

    def test_techsupport_l3(self):
        assert detect_role_type("L3 Support Analyst") == "techsupport"

    def test_infra_infrastructure_engineer(self):
        assert detect_role_type("Infrastructure Engineer") == "infra"

    def test_infra_systems_engineer(self):
        assert detect_role_type("Systems Engineer") == "infra"

    def test_infra_release_engineer(self):
        assert detect_role_type("Release Engineer") == "infra"

    def test_infra_operations_engineer(self):
        assert detect_role_type("Operations Engineer") == "infra"

    def test_fallback_to_other(self):
        assert detect_role_type("Talent Acquisition Manager") == "other"

    def test_generic_engineer_is_other(self):
        assert detect_role_type("Engineering Manager AI Fleet") == "other"


# ---------------------------------------------------------------------------
# detect_experience_level
# ---------------------------------------------------------------------------

class TestDetectExperienceLevel:
    def test_staff_from_staff(self):
        assert detect_experience_level("Staff DevOps Engineer") == "staff"

    def test_staff_from_principal(self):
        assert detect_experience_level("Principal SRE") == "staff"

    def test_staff_from_lead(self):
        assert detect_experience_level("Lead Platform Engineer") == "staff"

    def test_staff_from_director(self):
        assert detect_experience_level("Director of Infrastructure") == "staff"

    def test_senior(self):
        assert detect_experience_level("Senior Cloud Engineer") == "senior"

    def test_senior_abbreviated(self):
        assert detect_experience_level("Sr. SRE") == "senior"

    def test_entry_junior(self):
        assert detect_experience_level("Junior DevOps Engineer") == "entry"

    def test_entry_associate(self):
        assert detect_experience_level("Associate Platform Engineer") == "entry"

    def test_entry_graduate(self):
        assert detect_experience_level("Graduate Infrastructure Engineer") == "entry"

    def test_mid_fallback(self):
        assert detect_experience_level("DevOps Engineer") == "mid"

    def test_mid_from_description(self):
        assert detect_experience_level("SRE", "3 years of experience required") == "mid"

    def test_senior_in_description(self):
        assert detect_experience_level("Cloud Engineer", "senior role with 5+ years") == "senior"

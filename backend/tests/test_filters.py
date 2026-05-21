import pytest
from scraper.filters import detect_experience_level, detect_role_type, matches_keyword


# ---------------------------------------------------------------------------
# matches_keyword
# ---------------------------------------------------------------------------

class TestMatchesKeyword:
    # --- Positive matches ---
    def test_matches_devops_in_title(self):
        assert matches_keyword("Senior DevOps Engineer") is True

    def test_matches_sre_in_title(self):
        assert matches_keyword("Site Reliability Engineer") is True

    def test_matches_keyword_in_description_only(self):
        assert matches_keyword("Software Engineer", "looking for a platform engineer") is True

    def test_matches_case_insensitive(self):
        assert matches_keyword("CLOUD ENGINEER") is True

    def test_matches_devsecops(self):
        assert matches_keyword("DevSecOps Lead") is True

    def test_matches_infra_engineer(self):
        assert matches_keyword("Infrastructure Engineer III") is True

    def test_matches_release_engineer(self):
        assert matches_keyword("Release Engineer") is True

    def test_matches_mlops(self):
        assert matches_keyword("MLOps Engineer") is True

    def test_matches_ml_engineer(self):
        assert matches_keyword("ML Engineer") is True

    def test_matches_sysadmin(self):
        assert matches_keyword("Sysadmin") is True

    def test_matches_systems_administrator(self):
        assert matches_keyword("Systems Administrator") is True

    def test_matches_network_engineer(self):
        assert matches_keyword("Network Engineer") is True

    def test_matches_observability_engineer(self):
        assert matches_keyword("Observability Engineer") is True

    def test_matches_monitoring_engineer(self):
        assert matches_keyword("Monitoring Engineer") is True

    def test_matches_dba(self):
        assert matches_keyword("DBA") is True

    def test_matches_database_administrator(self):
        assert matches_keyword("Database Administrator") is True

    def test_matches_it_operations(self):
        assert matches_keyword("IT Operations Analyst") is True

    def test_matches_service_desk(self):
        assert matches_keyword("Service Desk Analyst") is True

    def test_matches_helpdesk(self):
        assert matches_keyword("Helpdesk Technician") is True

    def test_matches_help_desk(self):
        assert matches_keyword("Help Desk Support") is True

    def test_matches_it_support(self):
        assert matches_keyword("IT Support Specialist") is True

    def test_matches_production_engineer(self):
        assert matches_keyword("Production Engineer") is True

    def test_matches_l2_support(self):
        assert matches_keyword("L2 Support Analyst") is True

    def test_matches_ci_cd_engineer(self):
        assert matches_keyword("CI/CD Engineer") is True

    def test_matches_build_engineer(self):
        assert matches_keyword("Build Engineer") is True

    def test_matches_gitops(self):
        assert matches_keyword("GitOps Specialist") is True

    def test_matches_platform_operations(self):
        assert matches_keyword("Platform Operations Engineer") is True

    # --- Negative matches ---
    def test_no_match_unrelated_title(self):
        assert matches_keyword("Frontend React Developer") is False

    def test_no_match_empty_inputs(self):
        assert matches_keyword("", "") is False

    def test_no_match_engineer_alone(self):
        # "engineer" by itself must NOT match — requires the full phrase
        assert matches_keyword("Software Engineer") is False

    def test_no_match_cloud_alone(self):
        # "cloud" alone must NOT match
        assert matches_keyword("Cloud Manager") is False

    def test_no_match_support_alone(self):
        # "support" alone must NOT match
        assert matches_keyword("Support Analyst") is False

    def test_no_match_manager(self):
        assert matches_keyword("Engineering Manager AI Fleet") is False

    def test_no_match_data_engineer(self):
        assert matches_keyword("Data Engineer") is False


# ---------------------------------------------------------------------------
# detect_role_type
# ---------------------------------------------------------------------------

class TestDetectRoleType:
    # --- DevOps ---
    def test_devops(self):
        assert detect_role_type("DevOps Engineer") == "devops"

    def test_devops_devsecops(self):
        assert detect_role_type("DevSecOps Engineer") == "devops"

    def test_devops_gitops(self):
        assert detect_role_type("GitOps Engineer") == "devops"

    def test_devops_release_engineer(self):
        assert detect_role_type("Release Engineer") == "devops"

    def test_devops_build_engineer(self):
        assert detect_role_type("Build Engineer") == "devops"

    def test_devops_ci_cd_engineer(self):
        assert detect_role_type("CI/CD Engineer") == "devops"

    # --- SRE ---
    def test_sre(self):
        assert detect_role_type("Senior SRE") == "sre"

    def test_sre_full_name(self):
        assert detect_role_type("Site Reliability Engineer") == "sre"

    def test_sre_production_engineer(self):
        assert detect_role_type("Production Engineer") == "sre"

    # --- Platform ---
    def test_platform(self):
        assert detect_role_type("Platform Engineer") == "platform"

    def test_platform_engineering(self):
        assert detect_role_type("Head of Platform Engineering") == "platform"

    def test_platform_operations(self):
        assert detect_role_type("Platform Operations Manager") == "platform"

    # --- Cloud ---
    def test_cloud(self):
        assert detect_role_type("Cloud Engineer") == "cloud"

    def test_cloud_infrastructure(self):
        assert detect_role_type("Cloud Infrastructure Lead") == "cloud"

    def test_cloud_administrator(self):
        assert detect_role_type("Cloud Administrator") == "cloud"

    # --- Infra ---
    def test_infra_infrastructure_engineer(self):
        assert detect_role_type("Infrastructure Engineer") == "infra"

    def test_infra_systems_engineer(self):
        assert detect_role_type("Systems Engineer") == "infra"

    def test_infra_sysadmin(self):
        assert detect_role_type("Sysadmin") == "infra"

    def test_infra_systems_administrator(self):
        assert detect_role_type("Systems Administrator") == "infra"

    def test_infra_network_engineer(self):
        assert detect_role_type("Network Engineer") == "infra"

    def test_infra_observability_engineer(self):
        assert detect_role_type("Observability Engineer") == "infra"

    def test_infra_monitoring_engineer(self):
        assert detect_role_type("Monitoring Engineer") == "infra"

    # --- MLOps ---
    def test_mlops(self):
        assert detect_role_type("MLOps Engineer") == "mlops"

    def test_mlops_ml_engineer(self):
        assert detect_role_type("ML Engineer") == "mlops"

    def test_mlops_ml_infrastructure(self):
        # "ML Infrastructure Engineer" contains "infrastructure engineer" → infra wins
        # (infra patterns have higher priority than mlops in the map)
        assert detect_role_type("ML Infrastructure Engineer") == "infra"

    def test_mlops_ml_platform(self):
        # "ML Platform Engineer" contains "platform engineer" → platform wins
        assert detect_role_type("ML Platform Engineer") == "platform"

    def test_mlops_pure_title(self):
        assert detect_role_type("MLOps Architect") == "mlops"

    # --- Application Support ---
    def test_appsupport(self):
        assert detect_role_type("Application Support Analyst") == "appsupport"

    def test_appsupport_short(self):
        assert detect_role_type("App Support Engineer") == "appsupport"

    # --- Tech Support ---
    def test_techsupport(self):
        assert detect_role_type("Technical Support Engineer") == "techsupport"

    def test_techsupport_l1(self):
        assert detect_role_type("L1 Support Specialist") == "techsupport"

    def test_techsupport_l2(self):
        assert detect_role_type("L2 Support Engineer") == "techsupport"

    def test_techsupport_l3(self):
        assert detect_role_type("L3 Support Analyst") == "techsupport"

    def test_techsupport_service_desk(self):
        assert detect_role_type("Service Desk Agent") == "techsupport"

    def test_techsupport_helpdesk(self):
        assert detect_role_type("Helpdesk Technician") == "techsupport"

    def test_techsupport_it_support(self):
        assert detect_role_type("IT Support Specialist") == "techsupport"

    # --- IT Ops ---
    def test_itops_operations_engineer(self):
        assert detect_role_type("Operations Engineer") == "itops"

    def test_itops_it_operations(self):
        assert detect_role_type("IT Operations Analyst") == "itops"

    def test_itops_itops(self):
        assert detect_role_type("ITOps Engineer") == "itops"

    def test_itops_dba(self):
        assert detect_role_type("DBA") == "itops"

    def test_itops_database_administrator(self):
        assert detect_role_type("Database Administrator") == "itops"

    # --- Fallback ---
    def test_fallback_to_other(self):
        assert detect_role_type("Talent Acquisition Manager") == "other"

    def test_generic_engineer_is_other(self):
        assert detect_role_type("Engineering Manager AI Fleet") == "other"

    def test_cloud_alone_is_other(self):
        assert detect_role_type("Cloud Manager") == "other"

    def test_support_alone_is_other(self):
        assert detect_role_type("Support Analyst") == "other"


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

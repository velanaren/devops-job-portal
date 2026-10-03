"""
Real-world title corpus for the keyword filter (TASK-041).

Each title is labelled with the expected role_type, or 'other' when it must
be rejected. Edit this table when tuning keywords — it is the fast check that
a change did not add noise or drop real roles.
"""
import pytest

from scraper.filters import detect_role_type, matched_keyword, matches_keyword

CORPUS: list[tuple[str, str]] = [
    # --- should match ------------------------------------------------------
    ("Senior DevOps Engineer", "devops"),
    ("DevSecOps Architect", "devops"),
    ("Build & Release Engineer", "devops"),
    ("Release Engineering Manager", "devops"),
    ("CI/CD Engineer", "devops"),
    ("Developer Productivity Engineer", "devops"),
    ("Kubernetes Engineer", "devops"),
    ("Terraform Engineer (Contract)", "devops"),
    ("Site Reliability Engineer II", "sre"),
    ("SRE - Payments", "sre"),
    ("Production Engineer, Infrastructure", "sre"),
    ("Database Reliability Engineer", "sre"),
    ("Staff Platform Engineer", "platform"),
    ("Platform Engineering Lead", "platform"),
    ("Cloud Engineer - AWS", "cloud"),
    ("CloudOps Engineer", "cloud"),
    ("Cloud Security Engineer", "cloud"),
    ("AWS Architect", "cloud"),
    ("FinOps Analyst", "cloud"),
    ("Infrastructure Engineer III", "infra"),
    ("Infra Lead", "infra"),
    ("Linux Administrator", "infra"),
    ("Linux Systems Engineer", "infra"),
    ("Systems Engineer - Linux", "infra"),
    ("Network Engineer", "infra"),
    ("Observability Lead", "infra"),
    ("Storage Engineer", "infra"),
    ("MLOps Engineer", "mlops"),
    ("ML Platform Engineer", "platform"),
    ("Machine Learning Infrastructure Engineer", "infra"),
    ("LLMOps Engineer", "mlops"),
    ("Application Support Analyst", "appsupport"),
    ("Production Support Engineer", "appsupport"),
    ("L2 Support Engineer", "techsupport"),
    ("Cloud Support Engineer", "techsupport"),
    ("NOC Engineer", "techsupport"),
    ("Technical Support Engineer", "techsupport"),
    ("IT Operations Analyst", "itops"),
    ("Database Administrator (Oracle)", "itops"),
    ("Service Desk Analyst", "itops"),
    ("Desktop Support Engineer", "itops"),
    # --- should be rejected -----------------------------------------------
    ("Systems Engineer", "other"),
    ("Systems Engineer Trainee", "other"),
    ("Support Engineer", "other"),
    ("Customer Support Engineer", "other"),
    ("Customer Success Engineer - Cloud", "other"),
    ("Operations Engineer", "other"),
    ("Data Platform Engineer", "other"),
    ("Frontend Platform Engineer", "other"),
    ("Mobile Platform Engineer", "other"),
    ("Mechanical Reliability Engineer", "other"),
    ("Manufacturing Production Engineer", "other"),
    ("Process Engineer", "other"),
    ("Embedded Systems Engineer", "other"),
    ("DevOps Recruiter", "other"),
    ("Sales Engineer - Cloud", "other"),
    ("Video Production Engineer", "other"),
    ("ML Engineer", "other"),
    ("Software Engineer", "other"),
    ("Backend Engineer", "other"),
    ("Data Scientist", "other"),
]


@pytest.mark.parametrize("title,expected", CORPUS)
def test_corpus_role_type(title, expected):
    assert detect_role_type(title) == expected


@pytest.mark.parametrize("title,expected", CORPUS)
def test_corpus_matches_keyword_consistent(title, expected):
    # Every matched title must classify to a role, and vice versa.
    assert matches_keyword(title) is (expected != "other")


def test_matched_keyword_reports_phrase():
    assert matched_keyword("Senior Site Reliability Engineer") == "site reliability"
    assert matched_keyword("Data Platform Engineer") is None

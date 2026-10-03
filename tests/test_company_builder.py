"""Unit tests for company builder and LinkedIn size filter blocklist."""
import json
import tempfile
from pathlib import Path

import yaml

from job_hunt.company_builder import (
    build_companies_dataset,
    is_blocked_headcount,
    match_headcount,
)


def test_is_blocked_headcount():
    assert is_blocked_headcount("1-10 employees") is True
    assert is_blocked_headcount("11-50 employees") is True

    # Kept tiers
    assert is_blocked_headcount("51-200 employees") is False
    assert is_blocked_headcount("201-500 employees") is False
    assert is_blocked_headcount("501-1,000 employees") is False
    assert is_blocked_headcount("1,001-5,000 employees") is False
    assert is_blocked_headcount("5,001-10,000 employees") is False
    assert is_blocked_headcount("10,001+ employees") is False
    assert is_blocked_headcount("Unknown") is False
    assert is_blocked_headcount("") is False
    assert is_blocked_headcount(None) is False


def test_match_headcount():
    company_cache = {
        "razorpay": "1,001-5,000 employees",
        "postman": "501-1,000 employees",
        "setu": "11-50 employees",
        "target": "10,001+ employees",
    }
    slug_cache = {
        "rzp": "razorpay",
    }

    # Exact match
    assert match_headcount("Razorpay", "razorpay", company_cache, slug_cache) == "1,001-5,000 employees"
    # Suffix removal match
    assert match_headcount("Postman Technologies Pvt Ltd", "postman", company_cache, slug_cache) == "501-1,000 employees"
    # Slug cache match
    assert match_headcount("Razorpay Corp", "rzp", company_cache, slug_cache) == "1,001-5,000 employees"
    # Blocked match
    assert match_headcount("Setu", "setu", company_cache, slug_cache) == "11-50 employees"
    # Unknown
    assert match_headcount("Unknown Startup", "unknownstartup", company_cache, slug_cache) == "Unknown"


def test_build_companies_dataset():
    sample_yaml = {
        "greenhouse": [
            {"name": "Razorpay", "slug": "razorpay"},
            {"name": "Setu", "slug": "setu"},  # 11-50 employees -> block
        ],
        "lever": [
            {"name": "Razorpay", "slug": "razorpay"},  # Duplicate -> deduplicate
            {"name": "SmallCo", "slug": "smallco"},    # 1-10 employees -> block
            {"name": "MidCo", "slug": "midco"},        # 51-200 employees -> keep
        ],
        "ashby": [
            {"name": "UnlistedCo", "slug": "unlisted"}, # Unknown -> keep
        ]
    }
    sample_linkedin = {
        "companyCache": {
            "razorpay": "1,001-5,000 employees",
            "setu": "11-50 employees",
            "smallco": "1-10 employees",
            "midco": "51-200 employees",
        },
        "slugCache": {}
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "india.yml"
        yaml_path.write_text(yaml.dump(sample_yaml), encoding="utf-8")

        json_path = Path(tmpdir) / "linkedin.json"
        json_path.write_text(json.dumps(sample_linkedin), encoding="utf-8")

        out_path = Path(tmpdir) / "companies.json"

        companies = build_companies_dataset(
            yaml_path=str(yaml_path),
            linkedin_cache_path=str(json_path),
            output_path=str(out_path),
        )

        # Expected:
        # Razorpay (Greenhouse) -> kept
        # Setu (Greenhouse) -> blocked
        # Razorpay (Lever) -> deduplicated
        # SmallCo (Lever) -> blocked
        # MidCo (Lever) -> kept
        # UnlistedCo (Ashby) -> kept
        names = [c["name"] for c in companies]
        assert "Razorpay" in names
        assert "MidCo" in names
        assert "UnlistedCo" in names
        assert "Setu" not in names
        assert "SmallCo" not in names
        assert len(companies) == 3

        # Verify output JSON file
        saved = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(saved) == 3
        rzp = next(c for c in saved if c["name"] == "Razorpay")
        assert rzp["ats"] == "greenhouse"
        assert rzp["slug"] == "razorpay"
        assert rzp["headcount"] == "1,001-5,000 employees"

        unl = next(c for c in saved if c["name"] == "UnlistedCo")
        assert unl["headcount"] == "Unknown"

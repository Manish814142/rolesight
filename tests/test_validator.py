"""Unit tests for ATS slug validator and pruning script."""
import json
import tempfile
from pathlib import Path

from job_hunt.validator import (
    apply_known_corrections,
    probe_company,
    validate_and_prune,
)


def test_apply_known_corrections():
    companies = [
        {"name": "Razorpay", "ats": "greenhouse", "slug": "razorpay"},
        {"name": "Freshworks", "ats": "greenhouse", "slug": "freshworks"},
        {"name": "Slice", "ats": "ashby", "slug": "slice"},
    ]
    corrected = apply_known_corrections(companies)

    rzp = next(c for c in corrected if c["name"] == "Razorpay")
    assert rzp["ats"] == "greenhouse"
    assert rzp["slug"] == "razorpaysoftwareprivatelimited"

    fw = next(c for c in corrected if c["name"] == "Freshworks")
    assert fw["ats"] == "smartrecruiters"
    assert fw["slug"] == "freshworks"

    sl = next(c for c in corrected if c["name"] == "Slice")
    assert sl["ats"] == "lever"
    assert sl["slug"] == "sliceit"

    bs = next(c for c in corrected if c["name"] == "BrowserStack")
    assert bs["ats"] == "workday"
    assert bs["tenant"] == "browserstack"
    assert bs["dc"] == "wd3"
    assert bs["site"] == "External"


def test_probe_company_greenhouse_200(monkeypatch):
    class FakeResp:
        status_code = 200

    monkeypatch.setattr("job_hunt.validator.requests.get", lambda url, headers, timeout: FakeResp())
    company = {"name": "TestCo", "ats": "greenhouse", "slug": "testco"}
    ok, status = probe_company(company)
    assert ok is True
    assert status == 200


def test_probe_company_lever_404(monkeypatch):
    class FakeResp:
        status_code = 404

    monkeypatch.setattr("job_hunt.validator.requests.get", lambda url, headers, timeout: FakeResp())
    company = {"name": "TestCo", "ats": "lever", "slug": "testco"}
    ok, status = probe_company(company)
    assert ok is False
    assert status == 404


def test_probe_company_workday_200(monkeypatch):
    class FakeResp:
        status_code = 200

    monkeypatch.setattr("job_hunt.validator.requests.post", lambda url, json, headers, timeout: FakeResp())
    company = {"name": "BrowserStack", "ats": "workday", "tenant": "browserstack", "dc": "wd3", "site": "External"}
    ok, status = probe_company(company)
    assert ok is True
    assert status == 200


def test_validate_and_prune(monkeypatch):
    companies = [
        {"name": "ActiveCo", "ats": "greenhouse", "slug": "active"},
        {"name": "DeadCo", "ats": "lever", "slug": "dead"},
    ]

    def fake_probe(company, timeout=8.0):
        if company["name"] == "ActiveCo":
            return True, 200
        return False, 404

    monkeypatch.setattr("job_hunt.validator.probe_company", fake_probe)

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "companies.json"
        json_path.write_text(json.dumps(companies), encoding="utf-8")

        valid = validate_and_prune(companies_path=str(json_path))
        assert len(valid) == 1
        assert valid[0]["name"] == "ActiveCo"

        # Check rewritten file
        rewritten = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(rewritten) == 1
        assert rewritten[0]["name"] == "ActiveCo"


def test_probe_company_all_ats(monkeypatch):
    class FakeResp:
        status_code = 200

    monkeypatch.setattr("job_hunt.validator.requests.get", lambda url, headers, timeout: FakeResp())
    monkeypatch.setattr("job_hunt.validator.requests.post", lambda url, json, headers, timeout: FakeResp())

    # Smartrecruiters
    assert probe_company({"ats": "smartrecruiters", "slug": "sr"})[0] is True
    # Ashby
    assert probe_company({"ats": "ashby", "slug": "as"})[0] is True
    # Recruitee
    assert probe_company({"ats": "recruitee", "slug": "rc"})[0] is True
    # Personio
    assert probe_company({"ats": "personio", "slug": "pe"})[0] is True
    # Workday via slug colon format
    assert probe_company({"ats": "workday", "slug": "tenant:dc:site"})[0] is True
    # Unsupported ATS
    assert probe_company({"ats": "unknown_ats", "slug": "foo"})[0] is False


def test_probe_company_exception(monkeypatch):
    def boom(*args, **kwargs):
        raise ConnectionError("DNS failure")

    monkeypatch.setattr("job_hunt.validator.requests.get", boom)
    ok, err = probe_company({"ats": "greenhouse", "slug": "foo"})
    assert ok is False
    assert "DNS failure" in str(err)

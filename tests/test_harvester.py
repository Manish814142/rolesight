"""Unit tests for job_hunt/harvester.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from job_hunt.harvester import (
    ATS_PROBES,
    _probe,
    parse_workday_url,
    probe_slug_across_all_ats,
    probe_workday_tenant,
    run_harvest,
)

# ── _probe tests ─────────────────────────────────────────────────────────────

def test_probe_returns_true_on_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("job_hunt.harvester.requests.get", return_value=mock_resp):
        ok, status = _probe("GET", "https://example.com", None)
    assert ok is True
    assert status == 200


def test_probe_returns_false_on_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("job_hunt.harvester.requests.get", return_value=mock_resp):
        ok, status = _probe("GET", "https://example.com", None)
    assert ok is False
    assert status == 404


def test_probe_handles_connection_error():
    with patch("job_hunt.harvester.requests.get", side_effect=Exception("timeout")):
        ok, status = _probe("GET", "https://example.com", None)
    assert ok is False
    assert "timeout" in str(status)


def test_probe_post_uses_requests_post():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("job_hunt.harvester.requests.post", return_value=mock_resp) as mock_post:
        ok, status = _probe("POST", "https://example.com/jobs", {"limit": 1})
    mock_post.assert_called_once()
    assert ok is True


# ── parse_workday_url tests ───────────────────────────────────────────────────

def test_parse_workday_url_valid():
    url = "https://browserstack.wd3.myworkdayjobs.com/en-US/External"
    result = parse_workday_url(url)
    assert result == ("browserstack", "wd3", "External")


def test_parse_workday_url_no_locale():
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
    result = parse_workday_url(url)
    assert result is not None
    tenant, dc, site = result
    assert tenant == "nvidia"
    assert dc == "wd5"
    assert site == "NVIDIAExternalCareerSite"


def test_parse_workday_url_invalid():
    assert parse_workday_url("https://jobs.lever.co/cred") is None
    assert parse_workday_url("not-a-url") is None


# ── probe_slug_across_all_ats tests ──────────────────────────────────────────

def test_probe_slug_returns_hits_for_active_ats():
    """Mocks one ATS (greenhouse) returning 200 with jobs, rest returning 404."""
    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        if "greenhouse" in url:
            resp.status_code = 200
            resp.json.return_value = {"jobs": [{"id": 1, "title": "Dev"}]}
        else:
            resp.status_code = 404
        return resp

    with patch("job_hunt.harvester.requests.get", side_effect=fake_get):
        hits = probe_slug_across_all_ats("Acme Corp", "acme", "Unknown")

    assert len(hits) == 1
    assert hits[0]["ats"] == "greenhouse"
    assert hits[0]["slug"] == "acme"
    assert hits[0]["name"] == "Acme Corp"


def test_probe_slug_no_hits_on_all_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("job_hunt.harvester.requests.get", return_value=mock_resp):
        hits = probe_slug_across_all_ats("Acme Corp", "acme", "Unknown")
    assert hits == []


def test_probe_slug_multiple_ats_hits():
    """Two ATS engines return 200 with jobs: stops at first active ATS (greenhouse)."""
    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        if "greenhouse" in url:
            resp.status_code = 200
            resp.json.return_value = {"jobs": [{"id": 1}]}
        elif "lever" in url:
            resp.status_code = 200
            resp.json.return_value = [{"id": 2}]
        else:
            resp.status_code = 404
        return resp

    with patch("job_hunt.harvester.requests.get", side_effect=fake_get):
        hits = probe_slug_across_all_ats("MultiATS Co", "multiats", "501-1,000 employees")

    ats_list = [h["ats"] for h in hits]
    assert ats_list == ["greenhouse"]
    assert len(hits) == 1


# ── probe_workday_tenant tests ────────────────────────────────────────────────

def test_probe_workday_tenant_active():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"jobPostings": [{"title": "Engineer"}]}
    with patch("job_hunt.harvester.requests.post", return_value=mock_resp):
        entry = probe_workday_tenant(
            {"name": "BrowserStack", "tenant": "browserstack", "dc": "wd3", "site": "External"},
            "1,001-5,000 employees",
        )
    assert entry is not None
    assert entry["ats"] == "workday"
    assert entry["tenant"] == "browserstack"
    assert entry["dc"] == "wd3"
    assert entry["site"] == "External"


def test_probe_workday_tenant_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("job_hunt.harvester.requests.post", return_value=mock_resp):
        entry = probe_workday_tenant(
            {"name": "BadCo", "tenant": "badco", "dc": "wd1", "site": "External"},
            "Unknown",
        )
    assert entry is None


# ── ATS_PROBES constant tests ─────────────────────────────────────────────────

def test_all_seven_ats_engines_defined():
    expected = {"greenhouse", "lever", "ashby", "smartrecruiters", "recruitee", "workable", "personio"}
    assert set(ATS_PROBES.keys()) == expected


def test_ats_probe_urls_contain_slug():
    for ats, fn in ATS_PROBES.items():
        method, url, body = fn("testslug")
        assert "testslug" in url, f"{ats} URL does not embed slug"
        assert method == "GET"


# ── run_harvest integration test (full mock) ─────────────────────────────────

def test_run_harvest_writes_json(tmp_path):
    """run_harvest with mocked probes writes a valid companies.json."""
    yaml_content = "greenhouse:\n  - name: AcmeCorp\n    slug: acmecorp\n    tier: '1'\n"
    yaml_file = tmp_path / "india.yml"
    yaml_file.write_text(yaml_content)

    linkedin_data = {"companyCache": {}, "slugCache": {}, "slugOverrides": {}}
    linkedin_file = tmp_path / "linkedin.json"
    linkedin_file.write_text(json.dumps(linkedin_data))

    out_file = tmp_path / "companies.json"

    # Mock: greenhouse returns 200 with jobs, everything else returns 404, all Workday 404
    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        if "greenhouse" in url:
            resp.status_code = 200
            resp.json.return_value = {"jobs": [{"id": 1, "title": "Dev"}]}
        else:
            resp.status_code = 404
        return resp

    def fake_post(url, json=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 404
        return resp

    with patch("job_hunt.harvester.requests.get", side_effect=fake_get), \
         patch("job_hunt.harvester.requests.post", side_effect=fake_post):
        result = run_harvest(
            yaml_path=str(yaml_file),
            linkedin_path=str(linkedin_file),
            out_path=str(out_file),
            max_workers=2,
        )

    assert out_file.exists()
    saved = json.loads(out_file.read_text())
    assert len(saved) == 1
    assert saved[0]["name"] == "AcmeCorp"
    assert saved[0]["ats"] == "greenhouse"
    assert len(result) == 1


def test_harvester_main_cli_args(tmp_path: Path, monkeypatch) -> None:
    called_args = {}

    def fake_run_harvest(yaml_path, linkedin_path, out_path, max_workers):
        called_args["yaml"] = yaml_path
        called_args["linkedin"] = linkedin_path
        called_args["out"] = out_path
        called_args["workers"] = max_workers

    monkeypatch.setattr("job_hunt.harvester.run_harvest", fake_run_harvest)
    from job_hunt.harvester import main as harvester_main

    harvester_main([
        "--yaml", "my_yaml.yml",
        "--linkedin", "my_li.json",
        "--out", "my_out.json",
        "--workers", "15",
    ])

    assert called_args["yaml"] == "my_yaml.yml"
    assert called_args["linkedin"] == "my_li.json"
    assert called_args["out"] == "my_out.json"
    assert called_args["workers"] == 15


def test_run_harvest_with_workday_hit(tmp_path: Path) -> None:
    yaml_file = tmp_path / "india.yml"
    yaml_file.write_text("companies: []\n")
    linkedin_file = tmp_path / "linkedin.json"
    linkedin_file.write_text(json.dumps({"companyCache": {}}))
    out_file = tmp_path / "companies.json"

    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 404
        return resp

    def fake_post(url, json=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"jobPostings": [{"title": "Dev"}]}
        return resp

    with patch("job_hunt.harvester.requests.get", side_effect=fake_get), \
         patch("job_hunt.harvester.requests.post", side_effect=fake_post):
        result = run_harvest(
            yaml_path=str(yaml_file),
            linkedin_path=str(linkedin_file),
            out_path=str(out_file),
            max_workers=2,
        )

    assert out_file.exists()
    assert len(result) > 0
    assert result[0]["ats"] == "workday"


# ── _has_jobs tests across all 8 ATS engines ───────────────────────────────────

def test_has_jobs_validation():
    from job_hunt.harvester import _has_jobs

    def make_mock(status, json_data=None, text=""):
        m = MagicMock()
        m.status_code = status
        m.text = text
        m.content = text.encode("utf-8")
        if json_data is not None:
            m.json.return_value = json_data
        return m

    # 404 is always False
    assert not _has_jobs("greenhouse", make_mock(404))

    # Greenhouse
    assert _has_jobs("greenhouse", make_mock(200, {"jobs": [{"id": 1}]}))
    assert not _has_jobs("greenhouse", make_mock(200, {"jobs": []}))

    # Lever
    assert _has_jobs("lever", make_mock(200, [{"id": 1}]))
    assert not _has_jobs("lever", make_mock(200, []))

    # Ashby
    assert _has_jobs("ashby", make_mock(200, {"jobs": [{"id": 1}]}))
    assert not _has_jobs("ashby", make_mock(200, {"jobs": []}))

    # SmartRecruiters (must have totalFound > 0 and content > 0)
    assert _has_jobs("smartrecruiters", make_mock(200, {"totalFound": 5, "content": [{"id": 1}]}))
    assert not _has_jobs("smartrecruiters", make_mock(200, {"totalFound": 0, "content": []}))

    # Workable
    assert _has_jobs("workable", make_mock(200, {"jobs": [{"id": 1}]}))
    assert not _has_jobs("workable", make_mock(200, {"jobs": []}))

    # Recruitee
    assert _has_jobs("recruitee", make_mock(200, {"offers": [{"id": 1}]}))
    assert not _has_jobs("recruitee", make_mock(200, {"offers": []}))

    # Personio
    assert _has_jobs("personio", make_mock(200, text="<workzag-jobs><position><id>1</id></position></workzag-jobs>"))
    assert not _has_jobs("personio", make_mock(200, text="<html><body>no positions</body></html>"))

    # Workday
    assert _has_jobs("workday", make_mock(200, {"jobPostings": [{"title": "Eng"}]}))
    assert not _has_jobs("workday", make_mock(200, {"jobPostings": []}))




# ── declared-ATS preference & known corrections ──────────────────────────────

def _fake_get_active(active: dict):
    """active maps an ATS host fragment -> JSON payload with jobs; everything else 404s."""
    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        for frag, payload in active.items():
            if frag in url:
                resp.status_code = 200
                resp.json.return_value = payload
                return resp
        resp.status_code = 404
        return resp
    return fake_get


def test_probe_prefers_declared_ats_over_probe_order():
    """india.yml declares lever; greenhouse (earlier in probe order) also answers.
    The declared ATS must win — a same-slug board elsewhere may be another company."""
    from job_hunt.harvester import probe_slug_first_active_ats
    fake = _fake_get_active({"greenhouse": {"jobs": [{"id": 1}]}, "lever": [{"id": 2}]})
    with patch("job_hunt.harvester.requests.get", side_effect=fake):
        entry = probe_slug_first_active_ats("Zeta", "zeta", "Unknown", preferred_ats="lever")
    assert entry is not None
    assert entry["ats"] == "lever"
    assert "ats_fallback_from" not in entry


def test_probe_fallback_match_is_tagged_for_review():
    from job_hunt.harvester import probe_slug_first_active_ats
    fake = _fake_get_active({"greenhouse": {"jobs": [{"id": 1}]}})
    with patch("job_hunt.harvester.requests.get", side_effect=fake):
        entry = probe_slug_first_active_ats("Navi", "navi", "Unknown", preferred_ats="ashby")
    assert entry is not None
    assert entry["ats"] == "greenhouse"
    assert entry["ats_fallback_from"] == "ashby"


def test_load_candidates_keeps_declared_ats_and_applies_known_corrections(tmp_path):
    from job_hunt.harvester import load_candidates
    yml = tmp_path / "india.yml"
    yml.write_text(
        "greenhouse:\n  - name: Razorpay\n    slug: razorpay\n"
        "ashby:\n  - name: Acme\n    slug: acme\n"
    )
    cands = load_candidates(str(yml), str(tmp_path / "missing_linkedin.json"))
    assert ("Razorpay", "razorpaysoftwareprivatelimited", "Unknown", "greenhouse") in cands
    assert ("Acme", "acme", "Unknown", "ashby") in cands


def test_load_candidates_does_not_block_on_headcount(tmp_path):
    """LinkedIn headcount data is stale (e.g. Sigmoid tagged 11-50), so it is
    metadata only — never a reason to drop a company."""
    from job_hunt.harvester import load_candidates
    yml = tmp_path / "india.yml"
    yml.write_text("greenhouse:\n  - name: Sigmoid\n    slug: sigmoid\n")
    li = tmp_path / "linkedin.json"
    li.write_text(json.dumps({"companyCache": {"sigmoid": "11-50 employees"}, "slugCache": {}}))
    cands = load_candidates(str(yml), str(li))
    assert cands == [("Sigmoid", "sigmoid", "11-50 employees", "greenhouse")]

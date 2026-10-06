"""SmartRecruiters pagination, Workday cap, Amazon and Oracle HCM adapters (mocked HTTP)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_hunt.adapters import detect_ats, fetch_company_jobs


def _resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


# ── SmartRecruiters pagination ────────────────────────────────────────────────

@patch("requests.get")
def test_smartrecruiters_paginates_past_100(mock_get):
    """Swiggy had 168 postings but the adapter stopped at 100 (2026-10-05)."""
    def page(url, params=None, **kw):
        off = params["offset"]
        n = max(0, min(100, 168 - off))
        return _resp({"totalFound": 168, "content": [
            {"id": f"j{off + i}", "name": f"Backend Engineer {off + i}",
             "location": {"city": "Bengaluru", "country": "in"}, "releasedDate": "2026-10-01T00:00:00Z"}
            for i in range(n)]})
    mock_get.side_effect = page
    from job_hunt.adapters.smartrecruiters import fetch_smartrecruiters
    jobs = fetch_smartrecruiters("swiggy")
    assert len(jobs) == 168
    assert [c.kwargs["params"]["offset"] for c in mock_get.call_args_list] == [0, 100]


# ── Workday cap ───────────────────────────────────────────────────────────────

def test_workday_cap_covers_large_india_boards():
    """Nvidia had 276 and Target 302 India-search results; 100 was too low."""
    from job_hunt.adapters import workday
    assert workday.MAX_JOBS >= 500


# ── Amazon ────────────────────────────────────────────────────────────────────

def _amazon_job(i):
    return {"title": f"SDE II, Payments {i}", "normalized_location": "Bengaluru, Karnataka, IND",
            "posted_date": "October  1, 2026", "job_path": f"/en/jobs/{1000 + i}/sde-ii",
            "id_icims": str(1000 + i), "description_short": "Build Node.js services",
            "basic_qualifications": "- 3+ years of software development"}


@patch("requests.get")
def test_amazon_adapter_paginates_and_maps_fields(mock_get):
    def page(url, params=None, **kw):
        off = params["offset"]
        n = max(0, min(100, 150 - off))
        return _resp({"hits": 150, "jobs": [_amazon_job(off + i) for i in range(n)]})
    mock_get.side_effect = page
    jobs = fetch_company_jobs({"name": "Amazon", "ats": "amazon"})
    assert len(jobs) == 150
    j = jobs[0]
    assert (j.company, j.title, j.location) == ("Amazon", "SDE II, Payments 0", "Bengaluru, Karnataka, IND")
    assert j.url == "https://www.amazon.jobs/en/jobs/1000/sde-ii"
    assert j.posted_at == "2026-10-01"
    assert "3+ years" in j.description_text
    assert mock_get.call_args_list[0].kwargs["params"]["country"] == "IND"


@patch("requests.get")
def test_amazon_uses_the_full_description_not_the_202_char_stub(mock_get):
    """description_short is cut mid-sentence at 202 chars; `description` holds the whole text (T57)."""
    full = ("We build the sports data platform for Prime Video.<br/>Key job responsibilities<br/>"
            "- Design distributed services in Java or Python<br/>- Operate them on AWS")
    item = {**_amazon_job(0), "description": full, "description_short": full[:40]}
    mock_get.return_value = _resp({"hits": 1, "jobs": [item]})
    text = fetch_company_jobs({"name": "Amazon", "ats": "amazon"})[0].description_text
    assert "Design distributed services in Java or Python" in text and "Operate them on AWS" in text
    assert "<br" not in text
    assert text.index("sports data platform") < text.index("3+ years")        # role first, qualifications after
    assert text.count("We build the sports data") == 1                        # the stub is not repeated


@patch("requests.get")
def test_amazon_falls_back_to_the_stub_when_there_is_no_full_description(mock_get):
    item = {**_amazon_job(0), "description": "", "description_short": "Short blurb"}
    mock_get.return_value = _resp({"hits": 1, "jobs": [item]})
    assert "Short blurb" in fetch_company_jobs({"name": "Amazon", "ats": "amazon"})[0].description_text


# ── Oracle HCM ────────────────────────────────────────────────────────────────

BASE = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"


@patch("requests.get")
def test_oracle_hcm_filters_india_facet_and_paginates(mock_get):
    def page(url, params=None, **kw):
        finder = params["finder"]
        if "facetsList=LOCATIONS" in finder:
            return _resp({"items": [{"locationsFacet": [{"Id": 1, "Name": "United States"},
                                                        {"Id": 777, "Name": "India"}]}]})
        assert "selectedLocationsFacet=777" in finder
        off = int(finder.split("offset=")[1].split(",")[0])
        n = max(0, min(100, 130 - off))
        return _resp({"items": [{"TotalJobsCount": 130, "requisitionList": [
            {"Id": str(5000 + off + i), "Title": "Software Engineer III", "PostedDate": "2026-09-30",
             "PrimaryLocation": "Bengaluru, Karnataka, India", "ShortDescriptionStr": "Java/Node services"}
            for i in range(n)]}]})
    mock_get.side_effect = page
    jobs = fetch_company_jobs({"name": "JPMorgan Chase", "ats": "oracle_hcm",
                               "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"})
    assert len(jobs) == 130
    j = jobs[0]
    assert j.url == "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/5000"
    assert (j.company, j.posted_at, j.location) == ("JPMorgan Chase", "2026-09-30", "Bengaluru, Karnataka, India")


def test_detect_ats_recognises_oracle_hcm_and_workday_locale_urls():
    assert detect_ats("https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/requisitions") \
        == ("oracle_hcm", "ehpv.fa.em2.oraclecloud.com:CX_1")
    assert detect_ats("https://expedia.wd108.myworkdayjobs.com/en-US/search") == ("workday", "expedia:wd108:search")
    assert detect_ats("https://bb.wd3.myworkdayjobs.com/BlackBerry/jobs") == ("workday", "bb:wd3:BlackBerry")


def test_detect_ats_greenhouse_embed_url_uses_for_param():
    assert detect_ats("https://boards.greenhouse.io/embed/job_board?for=stripe&b=x") == ("greenhouse", "stripe")


def test_detect_ats_url_edge_cases_from_real_census():
    assert detect_ats("https://boards.greenhouse.io/embed/job_board/js?for=celigo") == ("greenhouse", "celigo")
    assert detect_ats("https://genpact.wd108.myworkdayjobs.com/External_Careers&source=x") \
        == ("workday", "genpact:wd108:External_Careers")

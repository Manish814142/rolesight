from unittest.mock import MagicMock, patch

from job_hunt.adapters import detect_ats
from job_hunt.adapters.ashby import fetch_ashby
from job_hunt.adapters.greenhouse import fetch_greenhouse
from job_hunt.adapters.lever import fetch_lever
from job_hunt.adapters.personio import fetch_personio
from job_hunt.adapters.recruitee import fetch_recruitee
from job_hunt.adapters.smartrecruiters import fetch_smartrecruiters
from job_hunt.adapters.workday import fetch_workday


def test_detect_ats():
    assert detect_ats("https://boards.greenhouse.io/stripe") == ("greenhouse", "stripe")
    assert detect_ats("https://boards.eu.greenhouse.io/groww") == ("greenhouse_eu", "groww")
    assert detect_ats("https://jobs.lever.co/spotify") == ("lever", "spotify")
    assert detect_ats("https://jobs.ashbyhq.com/ramp") == ("ashby", "ramp")
    assert detect_ats("https://jobs.smartrecruiters.com/Visa") == ("smartrecruiters", "Visa")
    assert detect_ats("https://proofpoint.wd1.myworkdayjobs.com/proofpointcareers") == ("workday", "proofpoint:wd1:proofpointcareers")
    assert detect_ats("https://bunq.recruitee.com") == ("recruitee", "bunq")
    assert detect_ats("https://personio.jobs.personio.de") == ("personio", "personio")
    assert detect_ats("https://customcompany.com/careers") is None

@patch("requests.get")
def test_fetch_greenhouse(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "jobs": [
            {
                "id": 101,
                "title": "Backend Engineer",
                "location": {"name": "Bengaluru, India"},
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/101",
                "content": "<p>Build payment infrastructure with Node.js.</p>",
                "updated_at": "2026-04-01T12:00:00Z"
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp
    
    jobs = fetch_greenhouse("stripe")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.ats == "greenhouse"
    assert job.company == "stripe"
    assert job.title == "Backend Engineer"
    assert "Bengaluru" in job.location
    assert "payment infrastructure" in job.description_text
    assert job.global_id == "greenhouse:stripe:101"

@patch("requests.get")
def test_fetch_lever(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "id": "lev-202",
            "text": "SDE - Platforms",
            "categories": {"location": "Remote", "commitment": "Full Time"},
            "hostedUrl": "https://jobs.lever.co/spotify/lev-202",
            "descriptionPlain": "Core distributed systems.",
            "createdAt": 1775000000000
        }
    ]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp
    
    jobs = fetch_lever("spotify")
    assert len(jobs) == 1
    assert jobs[0].ats == "lever"
    assert jobs[0].title == "SDE - Platforms"
    assert jobs[0].is_remote is True
    assert jobs[0].global_id == "lever:spotify:lev-202"

@patch("requests.get")
def test_fetch_ashby(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "jobs": [
            {
                "id": "ash-303",
                "title": "Software Engineer",
                "location": "Bengaluru",
                "isRemote": False,
                "jobUrl": "https://jobs.ashbyhq.com/ramp/ash-303",
                "descriptionPlain": "Build fintech workflows.",
                "publishedAt": "2026-04-01"
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp
    
    jobs = fetch_ashby("ramp")
    assert len(jobs) == 1
    assert jobs[0].ats == "ashby"
    assert jobs[0].global_id == "ashby:ramp:ash-303"

@patch("requests.get")
def test_fetch_smartrecruiters(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [
            {
                "id": "sr-404",
                "name": "API Developer",
                "location": {"city": "Bengaluru", "country": "India"},
                "releasedDate": "2026-03-20"
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp
    
    jobs = fetch_smartrecruiters("Visa")
    assert len(jobs) == 1
    assert jobs[0].ats == "smartrecruiters"
    assert jobs[0].title == "API Developer"
    assert jobs[0].global_id == "smartrecruiters:Visa:sr-404"

@patch("requests.post")
def test_fetch_workday(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "total": 1,
        "jobPostings": [
            {
                "bulletFields": ["JR-101"],
                "title": "Full Stack Engineer",
                "locationsText": "Noida, India",
                "externalPath": "/job/Noida/Full-Stack-Engineer_JR-101",
                "postedOn": "Posted 2 Days Ago"
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp
    
    jobs = fetch_workday("adobe", "wd5", "external")
    assert len(jobs) == 1
    assert jobs[0].ats == "workday"
    assert jobs[0].title == "Full Stack Engineer"
    assert "Noida" in jobs[0].location

@patch("requests.get")
def test_fetch_recruitee(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "offers": [
            {
                "id": 505,
                "slug": "backend-eng",
                "title": "Backend Engineer",
                "location": "Remote, India",
                "careers_url": "https://bunq.recruitee.com/o/backend-eng",
                "description": "<p>API development</p>",
                "published_at": "2026-04-01"
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp
    
    jobs = fetch_recruitee("bunq")
    assert len(jobs) == 1
    assert jobs[0].ats == "recruitee"
    assert jobs[0].global_id == "recruitee:bunq:505"

@patch("requests.get")
def test_fetch_personio(mock_get):
    mock_resp = MagicMock()
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <workzag-jobs>
        <position>
            <id>606</id>
            <name>Node Developer</name>
            <office>Bengaluru</office>
            <department>Engineering</department>
            <createdAt>2026-04-01</createdAt>
            <jobDescriptions>
                <jobDescription>
                    <name>About the role</name>
                    <value><![CDATA[<p>Node.js microservices</p>]]></value>
                </jobDescription>
            </jobDescriptions>
        </position>
    </workzag-jobs>"""
    mock_resp.content = xml_content
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp
    
    jobs = fetch_personio("personio")
    assert len(jobs) == 1
    assert jobs[0].ats == "personio"
    assert jobs[0].title == "Node Developer"
    assert jobs[0].global_id == "personio:personio:606"


@patch("requests.get")
def test_fetch_adapters_404_handling(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    assert fetch_greenhouse("nonexistent") == []
    assert fetch_lever("nonexistent") == []
    assert fetch_ashby("nonexistent") == []
    assert fetch_smartrecruiters("nonexistent") == []
    assert fetch_recruitee("nonexistent") == []
    assert fetch_personio("nonexistent") == []
    from job_hunt.adapters.workable import fetch_workable
    assert fetch_workable("nonexistent") == []


@patch("requests.post")
def test_fetch_workday_404_handling(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_post.return_value = mock_resp

    assert fetch_workday("nonexistent", "wd1", "site") == []


@patch("requests.get")
def test_fetch_workable(mock_get):
    from job_hunt.adapters.workable import fetch_workable

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "name": "EatClub",
        "jobs": [
            {
                "id": "123",
                "shortcode": "ABC",
                "title": "Backend Engineer",
                "city": "Bengaluru",
                "country": "India",
                "telecommuting": True,
                "description": "<p>Node.js & Python backend</p>",
                "url": "https://apply.workable.com/j/ABC",
                "published_on": "2026-04-01",
            }
        ],
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    jobs = fetch_workable("eatclub")
    assert len(jobs) == 1
    assert jobs[0].ats == "workable"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].is_remote is True
    assert "Node.js" in jobs[0].description_text



def _wd_post(id_prefix, n, locations_text="Bengaluru, India"):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"jobPostings": [
        {"title": f"Software Engineer {id_prefix}{i}", "locationsText": locations_text,
         "externalPath": f"/job/Bengaluru/SE_{id_prefix}{i}", "bulletFields": [f"{id_prefix}{i}"]}
        for i in range(n)
    ]}
    return resp


@patch("requests.post")
def test_fetch_workday_searches_india_and_paginates(mock_post):
    mock_post.side_effect = [_wd_post("a", 20), _wd_post("b", 20), _wd_post("c", 7)]
    jobs = fetch_workday("adobe", "wd5", "external")
    assert len(jobs) == 47
    payloads = [c.kwargs["json"] for c in mock_post.call_args_list]
    assert [p["offset"] for p in payloads] == [0, 20, 40]
    assert all(p["searchText"] == "India" and p["limit"] == 20 for p in payloads)
    assert jobs[0].url == "https://adobe.wd5.myworkdayjobs.com/external/job/Bengaluru/SE_a0"


@patch("requests.post")
def test_fetch_workday_caps_at_max_jobs(mock_post):
    from job_hunt.adapters import workday
    pages = workday.MAX_JOBS // workday.PAGE_SIZE
    mock_post.side_effect = [_wd_post(f"p{k}_", 20) for k in range(pages + 5)]
    jobs = fetch_workday("nvidia", "wd5", "site")
    assert len(jobs) == workday.MAX_JOBS
    assert mock_post.call_count == pages


@patch("requests.post")
def test_fetch_workday_keeps_earlier_pages_when_later_page_fails(mock_post):
    mock_post.side_effect = [_wd_post("a", 20), Exception("timeout")]
    jobs = fetch_workday("adobe", "wd5", "external")
    assert len(jobs) == 20


@patch("requests.get")
@patch("requests.post")
def test_fetch_workday_resolves_multi_location_jobs(mock_post, mock_get):
    """'N Locations' hides the cities, so the location pre-filter would drop the job.
    The adapter reads the real locations (and description) from the job detail endpoint."""
    mock_post.return_value = _wd_post("m", 1, locations_text="5 Locations")
    detail = MagicMock()
    detail.status_code = 200
    detail.json.return_value = {"jobPostingInfo": {
        "location": "India, Remote",
        "additionalLocations": ["India, Mumbai", "India, Pune"],
        "jobDescription": "<p>Build <b>Node.js</b> services</p>",
    }}
    mock_get.return_value = detail

    jobs = fetch_workday("nvidia", "wd5", "site")

    assert mock_get.call_args.args[0] == "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/site/job/Bengaluru/SE_m0"
    assert jobs[0].location == "India, Remote; India, Mumbai; India, Pune"
    assert jobs[0].is_remote is True
    assert "Node.js" in jobs[0].description_text


@patch("requests.post")
def test_fetch_workday_stops_when_pages_repeat(mock_post):
    """Tenants like Sabre return the same jobs once offset exceeds their count.
    Verify that an identical page served at every offset stops within 2 requests
    and returns each posting exactly once."""
    mock_post.return_value = _wd_post("repeat", 20)
    jobs = fetch_workday("sabre", "wd5", "external")
    assert len(jobs) == 20
    assert mock_post.call_count <= 2
    urls = [j.url for j in jobs]
    assert len(urls) == len(set(urls))


@patch("requests.post")
def test_fetch_workday_stops_at_total(mock_post):
    """When total is provided, stop paging once offset >= total."""
    resp1 = _wd_post("p1", 20)
    resp1.json.return_value["total"] = 25
    resp2 = _wd_post("p2", 20)
    resp2.json.return_value["total"] = 25
    # If it kept paging past offset 20, it would request offset 40
    resp3 = _wd_post("p3", 20)
    resp3.json.return_value["total"] = 25
    mock_post.side_effect = [resp1, resp2, resp3]
    jobs = fetch_workday("company", "wd5", "site")
    assert len(jobs) == 40
    assert mock_post.call_count == 2


@patch("requests.get")
def test_greenhouse_posted_at_prefers_first_published(mock_get):
    """updated_at moves on every edit (182/200 Stripe jobs differed on 2026-10-04);
    first_published is the real posting date."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"jobs": [{
        "id": 7, "title": "Backend Engineer", "location": {"name": "Bengaluru"},
        "absolute_url": "https://x/7", "content": "",
        "first_published": "2026-09-03T13:30:34-04:00", "updated_at": "2026-09-25T16:45:00-04:00"}]}
    mock_get.return_value = mock_resp
    assert fetch_greenhouse("stripe")[0].posted_at == "2026-09-03T13:30:34-04:00"


@patch("requests.get")
def test_greenhouse_board_with_null_fields_does_not_crash_the_fetch(mock_get):
    """T111: a harvested board had `"location": {"name": null}`; `.strip()` on None killed a whole discovery run."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jobs": [
        {"id": 1, "title": "Backend Engineer", "location": {"name": None}, "content": None, "updated_at": "2026-10-01T00:00:00Z"},
        {"id": 2, "title": None, "location": None, "content": "<p>x</p>"},
        {"id": 3, "title": "Platform Engineer", "location": {"name": "Pune, India"}, "content": ""},
    ]}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    jobs = fetch_greenhouse("acme")

    assert [j.title for j in jobs] == ["Backend Engineer", "", "Platform Engineer"]
    assert [j.location for j in jobs] == ["Not specified", "Not specified", "Pune, India"]


def test_adapters_mark_incomplete_on_non_404_failures():
    """T155: Adapters call mark_incomplete on any failure other than 404 (5xx, timeout, bad JSON). 404 stays clean."""
    import requests

    from job_hunt.adapters import base
    from job_hunt.adapters.ashby import fetch_ashby
    from job_hunt.adapters.greenhouse import fetch_greenhouse
    from job_hunt.adapters.lever import fetch_lever
    from job_hunt.adapters.personio import fetch_personio
    from job_hunt.adapters.recruitee import fetch_recruitee
    from job_hunt.adapters.workable import fetch_workable

    # 1. 404 on greenhouse -> returns [] and leaves fetch_incomplete None
    base.begin_fetch()
    resp_404 = MagicMock(status_code=404)
    with patch("job_hunt.adapters.greenhouse.http_get", return_value=resp_404):
        assert fetch_greenhouse("stripe") == []
    assert base.fetch_incomplete() is None

    # 2. 503 on greenhouse -> returns [] and calls mark_incomplete
    base.begin_fetch()
    resp_503 = MagicMock(status_code=503)
    resp_503.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
    with patch("job_hunt.adapters.greenhouse.http_get", return_value=resp_503):
        assert fetch_greenhouse("stripe") == []
    assert "503" in (base.fetch_incomplete() or "")

    # 3. Timeout on lever -> returns [] and calls mark_incomplete
    base.begin_fetch()
    with patch("job_hunt.adapters.lever.http_get", side_effect=requests.Timeout("Connection timed out")):
        assert fetch_lever("spotify") == []
    assert base.fetch_incomplete() is not None

    # 4. Bad JSON on ashby -> returns [] and calls mark_incomplete
    base.begin_fetch()
    resp_bad_json = MagicMock(status_code=200)
    resp_bad_json.raise_for_status.return_value = None
    resp_bad_json.json.side_effect = ValueError("Expecting value: line 1 column 1")
    with patch("job_hunt.adapters.ashby.http_get", return_value=resp_bad_json):
        assert fetch_ashby("ramp") == []
    assert base.fetch_incomplete() is not None

    # 5. 500 on recruitee -> returns [] and calls mark_incomplete
    base.begin_fetch()
    resp_500 = MagicMock(status_code=500)
    resp_500.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    with patch("job_hunt.adapters.recruitee.http_get", return_value=resp_500):
        assert fetch_recruitee("bunq") == []
    assert "500" in (base.fetch_incomplete() or "")

    # 6. Invalid XML on personio -> returns [] and calls mark_incomplete
    base.begin_fetch()
    resp_bad_xml = MagicMock(status_code=200, content=b"invalid xml")
    resp_bad_xml.raise_for_status.return_value = None
    with patch("job_hunt.adapters.personio.http_get", return_value=resp_bad_xml):
        assert fetch_personio("personio") == []
    assert base.fetch_incomplete() is not None

    # 7. Non-429 failure on workable (e.g. 500) -> returns [] and calls mark_incomplete
    base.begin_fetch()
    resp_workable_500 = MagicMock(status_code=500)
    resp_workable_500.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    with patch("job_hunt.adapters.workable.http_get", return_value=resp_workable_500):
        assert fetch_workable("someco") == []
    assert "500" in (base.fetch_incomplete() or "")


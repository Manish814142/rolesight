"""T26: Phenom People careers sites (POST {host}/widgets search; description from the job page's JSON-LD).
Fixtures follow the real responses of careers.bcg.com recorded 2026-10-10; no network."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from job_hunt.adapters import ENRICHERS, base, enrich_job, fetch_company_jobs
from job_hunt.adapters.phenom import PAGE_SIZE, fetch_description, fetch_phenom
from job_hunt.models import JobPosting


def _item(i: int, title: str = "", location: str = "Bengaluru, India", multi: str = "", posted: str = "2026-10-06T00:00:00.000+0000") -> dict:
    return {"jobId": str(59900 + i), "reqId": str(59900 + i), "title": title or f"Software Engineer {i}", "country": "India",
            "city": location.split(",")[0], "location": location,
            "multi_location": multi or f"['{location}']", "postedDate": posted, "type": "Full-Time",
            "applyUrl": f"https://experiencedtalent.bcg.com/careerhub/explore/jobs/{790000 + i}?post_onboarding_pid=",
            "descriptionTeaser": "Exciting opportunity"}


def _page(items: list, total: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": 200, "totalHits": total, "refineSearch": {"totalHits": total, "data": {"jobs": items}}}
    resp.raise_for_status.return_value = None
    resp.iter_content.return_value = iter([b""])
    return resp


@patch("requests.post")
def test_fields_are_mapped(mock_post):
    mock_post.return_value = _page([_item(1, "Senior Backend Engineer", "Bengaluru, India",
                                          "['Bengaluru, India', 'Mumbai, India']")], 1)
    [job] = fetch_phenom("careers.bcg.com", "global/en", company="BCG")
    assert (job.ats, job.company, job.title) == ("phenom", "BCG", "Senior Backend Engineer")
    assert job.global_id == "phenom:careers.bcg.com:59901"
    assert job.url == "https://careers.bcg.com/global/en/job/59901"        # the public job page, not the ATS apply link
    assert job.location == "Bengaluru, India; Mumbai, India"
    assert job.posted_at == "2026-10-06" and job.is_remote is False and job.description_text == ""


@patch("requests.post")
def test_a_remote_location_sets_is_remote(mock_post):
    mock_post.return_value = _page([_item(1, location="Remote, India")], 1)
    assert fetch_phenom("h.example.com", "us/en")[0].is_remote is True


@patch("requests.post")
def test_the_search_is_scoped_to_india_and_pages_by_the_page_size(mock_post):
    mock_post.side_effect = [_page([_item(i) for i in range(PAGE_SIZE)], PAGE_SIZE + 3),
                             _page([_item(PAGE_SIZE + i) for i in range(3)], PAGE_SIZE + 3)]
    jobs = fetch_phenom("careers.bcg.com", "global/en")
    assert len(jobs) == PAGE_SIZE + 3
    calls = mock_post.call_args_list
    assert all(c.args[0] == "https://careers.bcg.com/widgets" for c in calls)
    bodies = [c.kwargs["json"] for c in calls]
    assert [b["from"] for b in bodies] == [0, PAGE_SIZE]
    for b in bodies:
        assert b["ddoKey"] == "refineSearch" and b["selected_fields"] == {"country": ["India"]} and b["size"] == PAGE_SIZE
        assert (b["country"], b["lang"]) == ("global", "en_global")        # from the site's locale path "global/en"


@patch("requests.post")
def test_locale_us_en_becomes_lang_en_us(mock_post):
    mock_post.return_value = _page([], 0)
    fetch_phenom("careers.fiserv.com", "us/en")
    body = mock_post.call_args.kwargs["json"]
    assert (body["country"], body["lang"]) == ("us", "en_us")


@patch("requests.post")
def test_stops_when_a_page_repeats_earlier_jobs(mock_post):
    page = [_item(i) for i in range(PAGE_SIZE)]
    mock_post.side_effect = [_page(page, 500), _page(page, 500), _page(page, 500)]
    assert len(fetch_phenom("h.example.com", "us/en")) == PAGE_SIZE
    assert mock_post.call_count == 2


@patch("requests.post")
def test_keeps_earlier_pages_and_marks_the_fetch_incomplete_when_a_later_page_fails(mock_post):
    mock_post.side_effect = [_page([_item(i) for i in range(PAGE_SIZE)], 3 * PAGE_SIZE), Exception("timeout")]
    base.begin_fetch()
    assert len(fetch_phenom("h.example.com", "us/en")) == PAGE_SIZE
    assert "page failed" in (base.fetch_incomplete() or "")


@patch("requests.post")
def test_a_site_that_is_not_phenom_returns_nothing(mock_post):
    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status.side_effect = Exception("404")
    resp.iter_content.return_value = iter([b""])
    mock_post.return_value = resp
    assert fetch_phenom("h.example.com", "us/en") == []


# -- descriptions: the job page carries a JSON-LD JobPosting whose description is entity-escaped HTML ---------------

def _job_page(description_html: str) -> str:
    ld = {"@context": "http://schema.org", "@type": "JobPosting", "title": "t", "description": description_html}
    other = {"@context": "http://schema.org", "@type": "BreadcrumbList"}
    return ('<html><head><script type="application/ld+json">' + json.dumps(other) + '</script>'
            '<script type="application/ld+json">' + json.dumps(ld) + '</script></head><body>x</body></html>')


def _phenom_job() -> JobPosting:
    return JobPosting(global_id="phenom:careers.bcg.com:59901", ats="phenom", company="BCG", title="t",
                      location="Bengaluru, India", is_remote=False, url="https://careers.bcg.com/global/en/job/59901")


@patch("requests.get")
def test_description_comes_from_the_json_ld_of_the_job_page(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = _job_page("&lt;p&gt;Build &lt;b&gt;Node.js&lt;/b&gt; services&lt;/p&gt;&lt;ul&gt;&lt;li&gt;3+ years&lt;/li&gt;&lt;/ul&gt;")
    resp.iter_content.return_value = iter([resp.text.encode()])
    mock_get.return_value = resp
    text = fetch_description(_phenom_job())
    assert "Node.js" in text and "3+ years" in text and "&lt;" not in text and "<p>" not in text
    assert mock_get.call_args.args[0] == "https://careers.bcg.com/global/en/job/59901"


@patch("requests.get")
def test_description_is_empty_without_a_job_posting_block_or_on_http_error(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "<html><script type=\"application/ld+json\">{\"@type\": \"BreadcrumbList\"}</script></html>"
    resp.iter_content.return_value = iter([resp.text.encode()])
    mock_get.return_value = resp
    assert fetch_description(_phenom_job()) == ""
    bad = MagicMock()
    bad.status_code = 500
    bad.iter_content.return_value = iter([b""])
    mock_get.return_value = bad
    assert fetch_description(_phenom_job()) == ""


def test_enricher_is_registered_and_never_raises(monkeypatch):
    assert "phenom" in ENRICHERS
    job = _phenom_job()
    monkeypatch.setitem(ENRICHERS, "phenom", lambda j: (_ for _ in ()).throw(RuntimeError("boom")))
    assert enrich_job(job) is job and job.description_text == ""


@patch("requests.post")
def test_fetch_company_jobs_dispatches_on_host_and_locale(mock_post):
    mock_post.return_value = _page([_item(1)], 1)
    jobs = fetch_company_jobs({"name": "BCG", "ats": "phenom", "host": "careers.bcg.com", "locale": "global/en"})
    assert [(j.company, j.url) for j in jobs] == [("BCG", "https://careers.bcg.com/global/en/job/59901")]


def test_fetch_company_jobs_needs_host_and_locale():
    assert fetch_company_jobs({"name": "BCG", "ats": "phenom", "host": "careers.bcg.com"}) == []
    assert fetch_company_jobs({"name": "BCG", "ats": "phenom", "locale": "global/en"}) == []


@pytest.mark.parametrize("locale", ["global", "global/en/x", "", "global//en"])
def test_a_malformed_locale_fetches_nothing(locale):
    assert fetch_company_jobs({"name": "BCG", "ats": "phenom", "host": "careers.bcg.com", "locale": locale}) == []

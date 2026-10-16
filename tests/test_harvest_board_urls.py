"""T111: scripts/harvest_board_urls.py turns the Internet Archive's list of job-board URLs into `discover` seed lines.

No network: the archive is stubbed. The URL parser is the project's own `detect_ats`, so what the script emits is what `discover`
reads.
"""
import importlib.util
from pathlib import Path

import pytest

from job_hunt.discovery import parse_seeds

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("harvest_board_urls", ROOT / "scripts" / "harvest_board_urls.py")
hb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hb)

EXISTING = [{"name": "Stripe", "ats": "greenhouse", "slug": "stripe"},
            {"name": "Intel", "ats": "workday", "tenant": "intel", "dc": "wd1", "site": "External"}]


def test_board_urls_become_exact_seed_lines_that_discover_reads_back():
    lines = hb.board_seeds(["https://boards.greenhouse.io/acme-corp", "https://jobs.lever.co/zed/",
                            "https://acme.recruitee.com", "https://globex.jobs.personio.de/"], [])
    assert lines == ["Acme | https://acme.recruitee.com | exact",                 # sorted by name, then URL
                     "Acme Corp | https://boards.greenhouse.io/acme-corp | exact",
                     "Globex | https://globex.jobs.personio.de | exact",
                     "Zed | https://jobs.lever.co/zed | exact"]
    seeds = parse_seeds("\n".join(lines))
    assert len(seeds) == 4 and all(s["exact"] for s in seeds)             # read back by the real parser


def test_workday_sites_are_exact_url_seeds_one_per_site_and_file_names_are_not_sites():
    lines = hb.board_seeds(["https://capitalone.wd12.myworkdayjobs.com/en-US/Capital_One",
                            "https://capitalone.wd12.myworkdayjobs.com/favicon.ico",
                            "https://acme.wd1.myworkdayjobs.com/robots.txt",
                            "https://acme.wd1.myworkdayjobs.com/wday"], [])
    assert lines == ["Capitalone | https://capitalone.wd12.myworkdayjobs.com/Capital_One | exact"]
    assert "workday" in parse_seeds(lines[0])[0]                          # detect_ats turns the URL into a tenant:dc:site seed
    two = hb.board_seeds(["https://capitalone.wd12.myworkdayjobs.com/Careers", "https://capitalone.wd12.myworkdayjobs.com/Campus"], [])
    assert len(parse_seeds("\n".join(two))) == 2                          # every site of a tenant reaches discover (it keeps the busiest)


def test_careers_and_jobs_are_ordinary_workday_site_names_but_not_ats_slugs():
    assert len(hb.board_seeds(["https://acme.wd1.myworkdayjobs.com/careers", "https://acme.wd1.myworkdayjobs.com/jobs"], [])) == 2
    assert hb.board_seeds(["https://boards.greenhouse.io/careers", "https://jobs.lever.co/jobs"], []) == []


@pytest.mark.parametrize("url", [
    "https://jobs.lever.co/$company", "https://jobs.lever.co/%20Foschini", "https://jobs.lever.co/*",
    "https://jobs.lever.co/043a89e8f0d2453a8f36f66042f722f3", "https://boards.greenhouse.io/embed",
    "https://boards.greenhouse.io/favicon.ico", "https://jobs.ashbyhq.com/12345", "https://jobs.lever.co/a",
    "https://boards.eu.greenhouse.io/euco",                               # an ATS the probe table has no entry for
    "https://example.com/careers", "not a url",
])
def test_template_junk_files_ids_and_unsupported_boards_are_dropped(url):
    assert hb.board_seeds([url], []) == []


def test_boards_already_in_companies_json_are_skipped_whatever_the_case():
    urls = ["https://boards.greenhouse.io/Stripe", "https://intel.wd1.myworkdayjobs.com/External",
            "https://intel.wd1.myworkdayjobs.com/Other_Site", "https://jobs.lever.co/stripe"]
    lines = hb.board_seeds(urls, EXISTING)
    assert lines == ["Intel | https://intel.wd1.myworkdayjobs.com/Other_Site | exact", "Stripe | https://jobs.lever.co/stripe | exact"]


def test_one_board_written_in_two_cases_is_one_seed_and_keeps_the_capitalised_spelling():
    lines = hb.board_seeds(["https://jobs.smartrecruiters.com/boschgroup", "https://jobs.smartrecruiters.com/BoschGroup"], [])
    assert lines == ["Boschgroup | https://jobs.smartrecruiters.com/BoschGroup | exact"]


def test_names_are_made_from_the_slug():
    assert [hb.pretty(s) for s in ("acme-corp", "rox_data", "ABB", "lyft")] == ["Acme Corp", "Rox Data", "ABB", "Lyft"]


class FakeSession:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        status, text = self.answers.pop(0)
        return type("R", (), {"status_code": status, "text": text})()


def test_fetch_urls_retries_a_gateway_error_then_returns_the_lines(monkeypatch):
    monkeypatch.setattr(hb.time, "sleep", lambda s: None)
    session = FakeSession([(504, "<html>"), (200, "https://jobs.lever.co/a1\n\nhttps://jobs.lever.co/b2\n")])
    assert hb.fetch_urls(hb.ARCHIVE_QUERIES["lever"], session=session) == ["https://jobs.lever.co/a1", "https://jobs.lever.co/b2"]
    assert len(session.calls) == 2 and session.calls[0]["matchType"] == "prefix"
    assert "statuscode:200" in session.calls[0]["filter"]               # boards that were alive when archived


def test_fetch_urls_gives_up_after_its_tries_and_says_so(monkeypatch):
    monkeypatch.setattr(hb.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="lever"):
        hb.fetch_urls(hb.ARCHIVE_QUERIES["lever"], session=FakeSession([(504, "x")] * hb.TRIES))


def test_main_writes_the_seeds_and_a_count_per_board(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hb, "fetch_urls", lambda query, session=None: {
        "lever": ["https://jobs.lever.co/zed", "https://jobs.lever.co/stripe"], "ashby": ["https://jobs.ashbyhq.com/plane"]}.get(query["name"], []))
    companies = tmp_path / "companies.json"
    companies.write_text('[{"name": "Stripe", "ats": "lever", "slug": "stripe"}]')
    out = tmp_path / "seeds.txt"
    assert hb.main(["--out", str(out), "--hosts", "lever,ashby", "--companies", str(companies)]) == 0
    assert out.read_text().splitlines() == ["Plane | https://jobs.ashbyhq.com/plane | exact", "Zed | https://jobs.lever.co/zed | exact"]
    printed = capsys.readouterr().out
    assert "lever" in printed and "ashby" in printed and "2 seed" in printed


def test_main_rejects_an_unknown_host_name(tmp_path, capsys):
    assert hb.main(["--out", str(tmp_path / "s.txt"), "--hosts", "lever,nonsense"]) == 2
    assert "nonsense" in capsys.readouterr().err

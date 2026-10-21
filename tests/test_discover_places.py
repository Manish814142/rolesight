"""T139 (T108 part 4): `discover` checks the person's places; entries carry them; the scan fetches an entry for its places."""
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

import job_hunt.discovery as disc
from job_hunt import places as pl
from job_hunt.models import JobPosting

RECENT = (date.today() - timedelta(days=10)).isoformat()
UK = pl.places_from_config({"candidate": {"countries": ["United Kingdom"]}})


@pytest.fixture(autouse=True)
def _india_after():
    yield
    pl.configure_places(pl.INDIA)


def _jp(location, title="Backend Engineer"):
    return JobPosting("g:1", "greenhouse", "Monzo", title, location, False, "https://x/1", "Monzo builds banking", RECENT)


def test_the_gate_follows_the_places():
    assert disc.accept_board("greenhouse", "monzo", 5, 0, True, 3) == (False, "no India jobs")
    with pl.using(UK):
        assert disc.accept_board("greenhouse", "monzo", 5, 0, True, 3) == (False, "no jobs in United Kingdom")
        assert disc.accept_board("greenhouse", "monzo", 5, 2, True, 3) == (True, "verified")


@patch("job_hunt.discovery.fetch_company_jobs")
def test_a_board_with_london_jobs_and_no_india_job(mock_fetch, monkeypatch):
    mock_fetch.return_value = [_jp("London, UK"), _jp("London, UK", title="Designer")]
    monkeypatch.setattr(disc, "_board_name", lambda ats, slug: "Monzo")
    row = disc.evaluate_board("Monzo", "greenhouse", "monzo")
    assert (row["accepted"], row["verdict"], row["place_jobs"]) == (False, "no India jobs", 0)
    with pl.using(UK):
        row = disc.evaluate_board("Monzo", "greenhouse", "monzo")
    assert (row["accepted"], row["place_jobs"], row["prefilter_pass"]) == (True, 2, 1)


def _stub_discovery(monkeypatch, location):
    monkeypatch.setattr(disc, "_probe", lambda method, url, body, ats=None: ("monzo" in url and ats == "greenhouse", 200))
    monkeypatch.setattr(disc, "fetch_company_jobs", lambda c: [_jp(location)])
    monkeypatch.setattr(disc, "_board_name", lambda ats, slug: "Monzo")
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))


def test_discover_for_other_places_writes_them_on_the_entry(monkeypatch):
    _stub_discovery(monkeypatch, "London, UK")
    verified, _ = disc.discover(disc.parse_seeds("Monzo\n"), workers=2, places=UK)
    assert verified == [{"name": "Monzo", "ats": "greenhouse", "slug": "monzo", "headcount": "Unknown",
                         "places": ["United Kingdom"]}]
    verified, rows = disc.discover(disc.parse_seeds("Monzo\n"), workers=2)            # India: London is not enough
    assert verified == [] and any(r.get("verdict") == "no India jobs" for r in rows)


def test_discover_for_india_writes_no_places(monkeypatch):
    _stub_discovery(monkeypatch, "Bengaluru, India")
    verified, _ = disc.discover(disc.parse_seeds("Monzo\n"), workers=2)
    assert verified and "places" not in verified[0]


def test_the_recheck_checks_each_entry_against_its_own_places(monkeypatch):
    seen = []

    def fake_fetch(c):
        seen.append((c["name"], pl.active_places().label()))
        return [_jp("London, UK")] if c["name"] == "Monzo" else [_jp("Pune, India")]
    monkeypatch.setattr(disc, "fetch_company_jobs", fake_fetch)
    entries = [{"name": "Monzo", "ats": "greenhouse", "slug": "monzo", "places": ["United Kingdom"]},
               {"name": "Acme", "ats": "greenhouse", "slug": "acme"}]
    kept, rows = disc.reverify_existing(entries, workers=2)
    assert [c["name"] for c in kept] == ["Monzo", "Acme"] and all(r["accepted"] for r in rows)
    assert sorted(seen) == [("Acme", "India"), ("Monzo", "United Kingdom")]


def _wd(locs):
    r = MagicMock()
    r.status_code = 200
    r.headers = {}
    r.json.return_value = {"total": len(locs), "jobPostings": [
        {"title": "Backend Engineer", "locationsText": loc, "externalPath": f"/job/{loc}"} for loc in locs]}
    return r


@patch("requests.post")
def test_the_workday_light_check_tries_each_term_until_one_shows_a_place(mock_post):
    answers = {"United Kingdom": _wd(["Austin, TX"]), "UK": _wd(["London, UK"])}
    mock_post.side_effect = lambda url, **kw: answers[kw["json"]["searchText"]]
    with pl.using(UK):
        row = disc.evaluate_workday("Acme", "acme", "wd5", "Ext")
    assert [c.kwargs["json"]["searchText"] for c in mock_post.call_args_list] == ["United Kingdom", "UK"]
    assert row["accepted"] is True and row["place_jobs"] == 1


@patch("requests.post")
@pytest.mark.parametrize("status", [404, 422])
def test_the_workday_light_check_stops_at_a_missing_board(mock_post, status):
    """T144: 24 countries are 24 search terms; a board or site that does not exist answers every one the same way."""
    r = MagicMock()
    r.status_code, r.headers = status, {}
    mock_post.return_value = r
    with pl.using(UK):
        row = disc.evaluate_workday("Gone", "gone", "wd5", "Ext")
    assert mock_post.call_count == 1 and row["accepted"] is False and f"HTTP {status}" in row["verdict"]


@patch("requests.post")
def test_the_workday_light_check_for_india_asks_once(mock_post):
    mock_post.return_value = _wd(["Pune, India"])
    assert disc.evaluate_workday("Acme", "acme", "wd5", "Ext")["accepted"] is True
    assert [c.kwargs["json"]["searchText"] for c in mock_post.call_args_list] == ["India"]


def test_places_flag_and_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "seeds.txt").write_text("Monzo\n")
    captured = {}
    monkeypatch.setattr(disc, "discover", lambda seeds, workers=40, places=None: captured.setdefault("p", pl.active_places()) and ([], []))
    disc.main(["--seeds", "seeds.txt", "--report", "r.csv", "--out", "v.json", "--places", "UK, Singapore"])
    assert captured["p"].label() == "United Kingdom, Singapore"
    assert "a board needs a job in United Kingdom, Singapore" in capsys.readouterr().out
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {"countries": ["Germany"]}}))
    captured.clear()
    disc.main(["--seeds", "seeds.txt", "--report", "r.csv", "--out", "v.json"])
    assert captured["p"].label() == "Germany"


def test_a_scan_fetches_an_entry_only_for_its_places(tmp_path, monkeypatch):
    from job_hunt import scanner
    from job_hunt.db import init_db
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    fetched = []
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: fetched.append(c["name"]) or [])
    companies = [{"name": "Acme", "ats": "greenhouse", "slug": "acme"},
                 {"name": "Monzo", "ats": "greenhouse", "slug": "monzo", "places": ["United Kingdom"]}]
    cfg = {"gemini_api_key": "k", "candidate": {"name": "T", "resume_path": "resume.md"}}
    scanner.run_scan(cfg, companies)
    assert fetched == ["Acme"]                                   # India: Monzo was accepted for the UK only
    fetched.clear()
    scanner.run_scan({**cfg, "candidate": {**cfg["candidate"], "countries": ["UK"]}}, companies)
    assert sorted(fetched) == ["Acme", "Monzo"]

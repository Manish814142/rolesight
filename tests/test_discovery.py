"""Unit tests for job_hunt/discovery.py (no network)."""
from __future__ import annotations

from job_hunt.discovery import (
    accept_board,
    merge_companies,
    name_matches,
    parse_seeds,
    slug_candidates,
)


def test_slug_candidates_joined_hyphenated_and_suffix_stripped():
    slugs = slug_candidates("Tower Research Capital")
    assert "towerresearchcapital" in slugs
    assert "tower-research-capital" in slugs
    assert "tower" in slugs  # distinctive first word (>= 5 chars)

    assert "razorpay" in slug_candidates("Razorpay Software Pvt Ltd")
    assert "deshaw" in slug_candidates("D. E. Shaw")
    assert len(set(slug_candidates("Acko"))) == len(slug_candidates("Acko"))  # no duplicates


def test_slug_candidates_skip_short_generic_first_word():
    assert "ola" not in slug_candidates("Ola Electric")  # < 5 chars, collision-prone
    assert "olaelectric" in slug_candidates("Ola Electric")


def test_parse_seeds_names_urls_workday_and_comments():
    text = """
    # comment
    Stripe
    Jupiter Money | https://jobs.lever.co/jupiter
    BlackBerry | workday | bb | wd3 | BlackBerry
    stripe
    """
    seeds = parse_seeds(text)
    assert [s["name"] for s in seeds] == ["Stripe", "Jupiter Money", "BlackBerry"]  # case-insensitive dedupe
    assert seeds[1]["url"] == "https://jobs.lever.co/jupiter"
    assert seeds[2]["workday"] == {"tenant": "bb", "dc": "wd3", "site": "BlackBerry"}


def test_name_matches_board_names():
    assert name_matches("Razorpay", "Razorpay Software Private Limited")
    assert name_matches("Tower Research Capital", "Tower Research Capital LLC")
    assert name_matches("Visa", "Visa")
    assert not name_matches("Tower Research Capital", "Tower Semiconductor")
    assert not name_matches("Navi", "Navigator Labs")


def test_accept_board_requires_jobs_india_identity_and_not_known_bad():
    ok = dict(ats="greenhouse", slug="stripe", jobs=716, india_jobs=42, identity_ok=True)
    assert accept_board(**ok) == (True, "verified")
    assert accept_board(**{**ok, "jobs": 0})[0] is False
    assert accept_board(**{**ok, "india_jobs": 0})[0] is False
    assert accept_board(**{**ok, "identity_ok": False})[0] is False
    assert accept_board(ats="ashby", slug="navi", jobs=3, india_jobs=1, identity_ok=True)[0] is False


def test_merge_keeps_existing_and_dedupes_by_name_and_board():
    existing = [{"name": "Stripe", "ats": "greenhouse", "slug": "stripe", "headcount": "10,001+ employees"}]
    new = [
        {"name": "stripe", "ats": "greenhouse", "slug": "stripe"},           # same name
        {"name": "Stripe India", "ats": "greenhouse", "slug": "stripe"},     # same board
        {"name": "Plane", "ats": "ashby", "slug": "plane"},
        {"name": "Intel", "ats": "workday", "tenant": "intel", "dc": "wd1", "site": "External"},
    ]
    merged = merge_companies(existing, new)
    assert [c["name"] for c in merged] == ["Plane", "Stripe", "Intel"]  # sorted by (ats, name)
    assert merged[1]["headcount"] == "10,001+ employees"                 # existing entry wins


def test_accept_board_rejects_stale_boards():
    """Abandoned SmartRecruiters boards (newest posting 2015-2020) still return 200 + jobs."""
    ok = dict(ats="smartrecruiters", slug="lendingkart", jobs=1, india_jobs=1, identity_ok=True)
    assert accept_board(**ok, newest_age_days=4200)[0] is False
    assert accept_board(**ok, newest_age_days=30) == (True, "verified")
    assert accept_board(**ok, newest_age_days=None) == (True, "verified")  # unknown dates: not penalised


def test_newest_age_days_parses_adapter_dates():
    from datetime import datetime, timezone

    from job_hunt.discovery import newest_age_days
    from job_hunt.models import JobPosting
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    jobs = [JobPosting("", "x", "c", "t", "l", False, "", posted_at=p)
            for p in ("2015-04-06T10:00:00.000Z", "2026-09-24T08:00:00-04:00", "Posted 26 Days Ago", "")]
    assert newest_age_days(jobs, now=now) == 10
    assert newest_age_days(jobs[2:], now=now) is None


def test_merge_dedupes_aliases_by_core_name():
    existing = [{"name": "Mindtickle", "ats": "lever", "slug": "mindtickle"}]
    new = [{"name": "Mindtickle India", "ats": "smartrecruiters", "slug": "mindtickle"},
           {"name": "Zeta Tech", "ats": "lever", "slug": "zeta"},
           {"name": "Zeta", "ats": "lever", "slug": "zeta-other"}]
    names = [c["name"] for c in merge_companies(existing, new)]
    assert names == ["Mindtickle", "Zeta Tech"]


def test_parse_seeds_allows_workday_entry_with_same_name():
    seeds = parse_seeds("Mastercard\nMastercard | workday | mastercard | wd1 | CorporateCareers\n")
    assert len(seeds) == 2 and seeds[1]["workday"]["tenant"] == "mastercard"
    assert seeds[1]["name"] == "Mastercard"


def test_reverify_existing_drops_entries_that_fail(monkeypatch):
    import job_hunt.discovery as d
    monkeypatch.setattr(d, "evaluate_board", lambda name, ats, slug, from_url=False: {
        "seed": name, "accepted": slug != "lendingkart", "verdict": "x", "ats": ats, "board": slug})
    monkeypatch.setattr(d, "evaluate_workday", lambda name, tenant, dc, site: {
        "seed": name, "accepted": True, "verdict": "verified", "ats": "workday", "board": tenant})
    existing = [{"name": "Lendingkart", "ats": "smartrecruiters", "slug": "lendingkart"},
                {"name": "Stripe", "ats": "greenhouse", "slug": "stripe"},
                {"name": "Intel", "ats": "workday", "tenant": "intel", "dc": "wd1", "site": "External"}]
    kept, rows = d.reverify_existing(existing)
    assert [c["name"] for c in kept] == ["Stripe", "Intel"]
    assert len(rows) == 3


# ── network-backed pieces, with requests / adapters mocked ────────────────────

import json  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

import job_hunt.discovery as disc  # noqa: E402
from job_hunt.models import JobPosting  # noqa: E402


def _resp(status=200, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    return r


def _jp(title="Backend Engineer", location="Bengaluru, India", desc="", posted="2026-09-30"):
    return JobPosting("g", "x", "c", title, location, False, "u", description_text=desc, posted_at=posted)


@patch("job_hunt.discovery.requests.get")
def test_board_name_per_ats(mock_get):
    mock_get.return_value = _resp(payload={"name": "Stripe"})
    assert disc._board_name("greenhouse", "stripe") == "Stripe"
    mock_get.return_value = _resp(payload={"content": [{"company": {"name": "Visa"}}]})
    assert disc._board_name("smartrecruiters", "visa") == "Visa"
    mock_get.return_value = _resp(payload={"name": "Hugging Face"})
    assert disc._board_name("workable", "huggingface") == "Hugging Face"
    assert disc._board_name("lever", "cred") is None            # Lever exposes no board name
    mock_get.side_effect = Exception("boom")
    assert disc._board_name("greenhouse", "x") is None


@patch("job_hunt.discovery._board_name")
def test_identity_sources(mock_name):
    assert disc._identity("Jupiter", "lever", "jupiter", [], from_url=True)[0] is True
    mock_name.return_value = "Tower Semiconductor"
    assert disc._identity("Tower Research Capital", "greenhouse", "tower", [], False)[0] is False
    mock_name.return_value = None
    jobs = [_jp(desc="Join Plane and build..."), _jp(desc="unrelated")]
    ok, how = disc._identity("Plane", "ashby", "plane", jobs, False)
    assert ok is True and how == "named in 1/2 job descriptions"
    assert disc._identity("Plane", "ashby", "plane", [_jp(desc="nothing here")], False)[0] is False


@patch("job_hunt.discovery._board_name", return_value=None)
@patch("job_hunt.discovery.fetch_company_jobs")
def test_evaluate_board_counts_and_verdict(mock_fetch, _name):
    mock_fetch.return_value = [
        _jp("Backend Engineer", desc="Acme backend"),
        _jp("Senior Manager", location="Austin, TX", desc="Acme"),
    ]
    row = disc.evaluate_board("Acme", "lever", "acme")
    assert (row["jobs"], row["india_jobs"], row["prefilter_pass"], row["accepted"]) == (2, 1, 1, True)
    mock_fetch.return_value = [_jp(desc="Acme", posted="2015-04-06")]
    assert disc.evaluate_board("Acme", "lever", "acme")["verdict"].startswith("stale board")


@patch("job_hunt.discovery.requests.post")
def test_evaluate_workday(mock_post):
    mock_post.return_value = _resp(payload={"jobPostings": [
        {"title": "Software Engineer", "locationsText": "Bangalore, India"},
        {"title": "Director", "locationsText": "Austin"}]})
    row = disc.evaluate_workday("Intel", "intel", "wd1", "External")
    assert row["accepted"] is True and row["india_jobs"] == 1 and row["prefilter_pass"] == 1
    assert row["entry"] == {"name": "Intel", "ats": "workday", "tenant": "intel", "dc": "wd1", "site": "External"}
    mock_post.return_value = _resp(status=422)
    row = disc.evaluate_workday("Walmart", "walmart", "wd5", "WalmartExternal")
    assert row["accepted"] is False and "HTTP 422" in row["verdict"]


def test_discover_picks_best_board_and_reports_misses(monkeypatch):
    monkeypatch.setattr(disc, "_probe", lambda method, url, body, ats=None: (
        ("acme" in url and ats in ("greenhouse", "lever")), 200))
    def fake_eval(name, ats, slug, from_url=False):
        india = {"greenhouse": 3, "lever": 9}[ats]
        return {"seed": name, "accepted": True, "verdict": "verified", "ats": ats, "board": slug,
                "jobs": 10, "india_jobs": india, "prefilter_pass": 1, "identity": "board name 'Acme'"}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)
    monkeypatch.setattr(disc, "evaluate_workday", lambda name, tenant, dc, site: {
        "seed": name, "accepted": True, "verdict": "verified", "ats": "workday", "board": tenant,
        "entry": {"name": name, "ats": "workday", "tenant": tenant, "dc": dc, "site": site}})
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    seeds = parse_seeds("Acme\nNowhere Corp\nIntel | workday | intel | wd1 | External\n")

    verified, rows = disc.discover(seeds, workers=4)

    by_name = {v["name"]: v for v in verified}
    assert by_name["Acme"]["ats"] == "lever"             # most India jobs wins
    assert by_name["Intel"]["tenant"] == "intel"
    assert "Nowhere Corp" not in by_name
    assert any(r["seed"] == "Nowhere Corp" and r["verdict"].startswith("no live board") for r in rows)


def test_main_writes_outputs_and_merges(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Plane\n")
    target = tmp_path / "companies.json"
    target.write_text(json.dumps([{"name": "Stale Co", "ats": "smartrecruiters", "slug": "stale"},
                                  {"name": "Stripe", "ats": "greenhouse", "slug": "stripe"}]))
    monkeypatch.setattr(disc, "discover", lambda s, workers=40: (
        [{"name": "Plane", "ats": "ashby", "slug": "plane", "headcount": "Unknown"}],
        [{"seed": "Plane", "verdict": "verified", "ats": "ashby", "board": "plane"}]))
    monkeypatch.setattr(disc, "evaluate_board", lambda name, ats, slug, from_url=False: {
        "seed": name, "accepted": slug != "stale", "verdict": "stale board" if slug == "stale" else "verified",
        "ats": ats, "board": slug})
    out, report = tmp_path / "v.json", tmp_path / "r.csv"

    disc.main(["--seeds", str(seeds), "--out", str(out), "--report", str(report), "--merge", str(target)])

    assert json.loads(out.read_text())[0]["name"] == "Plane"
    assert [c["name"] for c in json.loads(target.read_text())] == ["Plane", "Stripe"]
    assert "[existing] Stale Co" in report.read_text()

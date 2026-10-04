"""Unit tests for job_hunt/discovery.py (no network)."""
from __future__ import annotations

import pytest

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


# ── paste parsing & legal-name variants (formats seen in real pastes) ─────────

from job_hunt.discovery import extract_company_names, name_variants  # noqa: E402

PASTE = """
F = Facebook = http://bit.ly/2Ni3PTr
10. Codenation = http://bit.ly/3p4BZrN
40. Toppr = https://apply.workable.com/toppr/?lng=en
Sahaj August/sept
Amazon(intern)    september
𝐃𝐢𝐫𝐞𝐜𝐭𝐢:  Basic 16.4L / CTC 27.45L - (𝗦𝗗𝗘1)
Company\tRole\tCTC\tTC(First Year)
Squarepoint Capital\tInfrastructure Engineer\t₹ 66,13,882\t₹60,83,882
Index No\tCompany Name\tRole\tCTC (In Lakh)
1\tTower Research\t\t44\t4,00,000\tSalary: 3,000,000 INR
<li><a href="https://jobs.lever.co/jupiter">Jupiter money</a>  </li>
OLA (ANI Technologies Private Limited)
FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)
Squarepoint Capital
"""


def test_extract_company_names_handles_real_paste_formats():
    got = extract_company_names(PASTE)
    names = [n for n, _ in got]
    assert names == ["Facebook", "Codenation", "Toppr", "Sahaj", "Amazon", "Directi",
                     "Squarepoint Capital", "Tower Research", "Jupiter money",
                     "OLA (ANI Technologies Private Limited)",
                     "FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)"]
    urls = dict(got)
    assert urls["Toppr"] == "https://apply.workable.com/toppr/?lng=en"
    assert urls["Jupiter money"] == "https://jobs.lever.co/jupiter"
    assert urls["Facebook"] == "http://bit.ly/2Ni3PTr"


def test_name_variants_and_display_name():
    assert name_variants("OLA (ANI Technologies Private Limited)") == ["OLA", "ANI Technologies Private Limited"]
    assert disc.display_name("FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)") == "Meesho"
    assert disc.display_name("Quadeye (QE Securities LLP)") == "Quadeye"
    assert disc.display_name("Stripe") == "Stripe"


def test_slug_candidates_cover_brand_in_parentheses_and_llp():
    assert "meesho" in slug_candidates("FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)")
    assert "ola" in slug_candidates("OLA (ANI Technologies Private Limited)")  # a variant is the whole brand
    assert "gravitonresearchcapital" in slug_candidates("Graviton Research Capital LLP")


def test_identity_accepts_brand_variant():
    assert name_matches("FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)", "Meesho")


def test_main_add_mode_verifies_only_new_names_and_appends_seeds(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Stripe\n")
    add = tmp_path / "paste.txt"
    add.write_text("Plane\nstripe\nFASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)\n")
    seen = {}

    def fake_discover(s, workers=40):
        seen["names"] = [x["name"] for x in s]
        return [], []
    monkeypatch.setattr(disc, "discover", fake_discover)

    disc.main(["--seeds", str(seeds), "--add-file", str(add), "--out", str(tmp_path / "v.json"),
               "--report", str(tmp_path / "r.csv")])

    assert seen["names"] == ["Plane", "stripe", "FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)"]  # all pasted names verified
    text = seeds.read_text()
    assert "Plane" in text and "FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)" in text
    assert text.lower().count("stripe") == 1                                                    # not re-appended


def test_add_mode_accepts_seed_format_lines_including_workday(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Stripe\n")
    add = tmp_path / "paste.txt"
    add.write_text("Medtronic | workday | medtronic | wd1 | MedtronicCareers\nJupiter | https://jobs.lever.co/jupiter\nPlane\n")
    seen = {}

    def fake_discover(s, workers=40):
        seen["seeds"] = s
        return [], []
    monkeypatch.setattr(disc, "discover", fake_discover)

    disc.main(["--seeds", str(seeds), "--add-file", str(add), "--out", str(tmp_path / "v.json"),
               "--report", str(tmp_path / "r.csv")])

    by_name = {s["name"]: s for s in seen["seeds"]}
    assert by_name["Medtronic"]["workday"] == {"tenant": "medtronic", "dc": "wd1", "site": "MedtronicCareers"}
    assert by_name["Jupiter"]["url"] == "https://jobs.lever.co/jupiter"
    assert "Plane" in by_name
    assert "Medtronic | workday | medtronic | wd1 | MedtronicCareers" in seeds.read_text()


def test_recheck_replaces_moved_boards_and_removes_dead_ones(tmp_path, monkeypatch):
    """Periodic re-check: a company whose board stopped verifying is re-discovered by
    name (e.g. it moved ATS); if nothing verifies it is removed and reported."""
    target = tmp_path / "companies.json"
    target.write_text(json.dumps([
        {"name": "Alive", "ats": "greenhouse", "slug": "alive", "headcount": "51-200 employees"},
        {"name": "Moved", "ats": "lever", "slug": "moved", "headcount": "1,001-5,000 employees"},
        {"name": "Gone", "ats": "smartrecruiters", "slug": "gone"},
    ]))
    monkeypatch.setattr(disc, "evaluate_board", lambda name, ats, slug, from_url=False: {
        "seed": name, "accepted": slug == "alive", "verdict": "verified" if slug == "alive" else "no open jobs",
        "ats": ats, "board": slug})

    def fake_discover(seeds, workers=40):
        assert sorted(s["name"] for s in seeds) == ["Gone", "Moved"]
        return ([{"name": "Moved", "ats": "ashby", "slug": "moved", "headcount": "Unknown"}],
                [{"seed": "Moved", "verdict": "verified", "ats": "ashby", "board": "moved"}])
    monkeypatch.setattr(disc, "discover", fake_discover)
    report = tmp_path / "r.csv"

    disc.main(["--recheck", "--merge", str(target), "--report", str(report), "--out", str(tmp_path / "v.json")])

    out = {c["name"]: c for c in json.loads(target.read_text())}
    assert set(out) == {"Alive", "Moved"}
    assert (out["Moved"]["ats"], out["Moved"]["headcount"]) == ("ashby", "1,001-5,000 employees")
    text = report.read_text()
    assert "Gone" in text and "Moved" in text


# ── ATS census: which platform does a careers page use? ───────────────────────

from job_hunt.discovery import fingerprint_ats  # noqa: E402


@pytest.mark.parametrize("text,platform", [
    ('<a href="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite">Jobs</a>', "workday"),
    ('<iframe src="https://boards.greenhouse.io/embed/job_board?for=stripe">', "greenhouse"),
    ('<a href="https://jobs.lever.co/cred">', "lever"),
    ('https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1', "oracle_hcm"),
    ('<script src="https://cdn.phenompeople.com/CareerConnectResources/x.js">', "phenom"),
    ('https://careers.microsoft.com -> https://apply.careers.microsoft.com/ (eightfold.ai)', "eightfold"),
    ('https://magicpin.darwinbox.in/ms/candidate/careers', "darwinbox"),
    ('https://career5.successfactors.eu/career?company=x', "successfactors"),
    ('https://benchmarkit.zohorecruit.com/jobs/Careers', "zoho_recruit"),
    ('https://spinny.freshteam.com/jobs', "freshteam"),
    ('https://acme.keka.com/careers/', "keka"),
    ('https://jobs.example.icims.com/jobs', "icims"),
    ('https://x.taleo.net/careersection', "taleo"),
    ('https://groww.skillate.com/', "skillate"),
    ('<p>Join us! Email careers@acme.com</p>', None),
])
def test_fingerprint_ats(text, platform):
    found = fingerprint_ats(text)
    assert (found[0] if found else None) == platform


def test_fingerprint_counts_job_boards_separately():
    found = fingerprint_ats('<a href="https://www.instahyre.com/jobs-at-apna/">x</a>')
    assert found == ["job_board:instahyre"]


@patch("job_hunt.discovery.requests.get")
def test_census_fetches_pages_and_reports_platform(mock_get, tmp_path):
    page = MagicMock()
    page.status_code = 200
    page.url = "https://careers.acme.com/"
    page.text = '<a href="https://jobs.lever.co/acme">Openings</a>'
    mock_get.return_value = page
    rows = disc.ats_census([{"name": "Acme", "url": "https://careers.acme.com"}], workers=2)
    assert rows == [{"seed": "Acme", "url": "https://careers.acme.com", "platform": "lever",
                     "all_platforms": "lever", "final_url": "https://careers.acme.com/", "verdict": "HTTP 200"}]
    mock_get.side_effect = Exception("blocked")
    assert disc.ats_census([{"name": "B", "url": "https://b"}])[0]["platform"] == "fetch failed"


@patch("job_hunt.discovery.requests.get")
def test_census_follows_job_links_one_level_when_landing_page_is_silent(mock_get):
    """Marketing careers pages often only link to an 'Open positions' page; the ATS
    shows up there."""
    def page(url, text):
        r = MagicMock()
        r.status_code, r.url, r.text = 200, url, text
        return r
    landing = page("https://acme.com/careers", '<a href="/careers/open-positions">See open positions</a>'
                                               '<a href="/about">About</a>')
    openings = page("https://acme.com/careers/open-positions",
                    '<script src="https://cdn.phenompeople.com/x.js"></script>')
    mock_get.side_effect = lambda url, **kw: openings if "open-positions" in url else landing

    row = disc.ats_census([{"name": "Acme", "url": "https://acme.com/careers"}])[0]

    assert row["platform"] == "phenom"
    assert row["verdict"].endswith("via https://acme.com/careers/open-positions")
    assert all("/about" not in c.args[0] for c in mock_get.call_args_list)

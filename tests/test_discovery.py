"""Unit tests for job_hunt/discovery.py (no network)."""
from __future__ import annotations

from datetime import date, timedelta

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
    ok = dict(ats="greenhouse", slug="stripe", jobs=716, place_jobs=42, identity_ok=True)
    assert accept_board(**ok) == (True, "verified")
    assert accept_board(**{**ok, "jobs": 0})[0] is False
    assert accept_board(**{**ok, "place_jobs": 0})[0] is False
    assert accept_board(**{**ok, "identity_ok": False})[0] is False
    assert accept_board(ats="ashby", slug="navi", jobs=3, place_jobs=1, identity_ok=True)[0] is False


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
    ok = dict(ats="smartrecruiters", slug="lendingkart", jobs=1, place_jobs=1, identity_ok=True)
    assert accept_board(**ok, newest_age_days=4200)[0] is False
    assert accept_board(**ok, newest_age_days=30) == (True, "verified")
    assert accept_board(**ok, newest_age_days=None) == (True, "verified")  # unknown dates: not penalised


def test_newest_age_days_parses_adapter_dates():
    from datetime import datetime

    from job_hunt.discovery import newest_age_days
    from job_hunt.models import JobPosting
    now = datetime(2026, 10, 4)         # naive = the local 2026-10-04 in any zone; a UTC moment would be the 3rd in the Americas (T110)
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


# Ten days ago, not a literal date: discover rejects a board whose newest posting is over 180 days old, so a fixed
# "2026-09-30" would have failed these tests from about April 2027 (review of T87).
RECENT = (date.today() - timedelta(days=10)).isoformat()


def _jp(title="Backend Engineer", location="Bengaluru, India", desc="", posted=RECENT):
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
    assert (row["jobs"], row["place_jobs"], row["prefilter_pass"], row["accepted"]) == (2, 1, 1, True)
    mock_fetch.return_value = [_jp(desc="Acme", posted="2015-04-06")]
    assert disc.evaluate_board("Acme", "lever", "acme")["verdict"].startswith("stale board")


@patch("job_hunt.discovery.requests.post")
def test_evaluate_workday(mock_post):
    mock_post.return_value = _resp(payload={"jobPostings": [
        {"title": "Software Engineer", "locationsText": "Bangalore, India"},
        {"title": "Director", "locationsText": "Austin"}]})
    row = disc.evaluate_workday("Intel", "intel", "wd1", "External")
    assert row["accepted"] is True and row["place_jobs"] == 1 and row["prefilter_pass"] == 1
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
                "jobs": 10, "place_jobs": india, "prefilter_pass": 1, "identity": "board name 'Acme'"}
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

    def fake_discover(seeds, workers=40, places=None):
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
                     "all_platforms": "lever", "board_url": "https://jobs.lever.co/acme",
                     "final_url": "https://careers.acme.com/", "verdict": "HTTP 200"}]
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


# ── census evidence → seeds; Workday/Oracle URL seeds; Oracle/Amazon verification ──

def test_parse_seeds_converts_workday_and_oracle_urls():
    seeds = parse_seeds("Visa | https://visa.wd1.myworkdayjobs.com/en-US/Visa\n"
                        "DP World | https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/requisitions\n"
                        "Upstox | https://jobs.lever.co/upstox\n")
    assert seeds[0]["workday"] == {"tenant": "visa", "dc": "wd1", "site": "Visa"}
    assert seeds[1]["oracle_hcm"] == {"host": "ehpv.fa.em2.oraclecloud.com", "site": "CX_1"}
    assert seeds[2]["url"] == "https://jobs.lever.co/upstox"


def test_census_records_board_url_evidence():
    text = '<a href="https://boards.greenhouse.io/twitter?gh_src=x">Jobs</a> <a href="https://x.com">X</a>'
    assert disc.evidence_url(text, "greenhouse") == "https://boards.greenhouse.io/twitter?gh_src=x"
    assert disc.evidence_url(text, "lever") == ""


def test_census_rows_to_seed_lines_only_for_supported_platforms():
    rows = [
        {"seed": "Twitter", "platform": "greenhouse", "board_url": "https://boards.greenhouse.io/twitter"},
        {"seed": "Visa", "platform": "workday", "board_url": "https://visa.wd1.myworkdayjobs.com/Visa"},
        {"seed": "DP World", "platform": "oracle_hcm",
         "board_url": "https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1"},
        {"seed": "eBay", "platform": "phenom", "board_url": "https://cdn.phenompeople.com/x.js"},
        {"seed": "Odd", "platform": "lever", "board_url": ""},
    ]
    assert disc.census_seed_lines(rows) == [
        "Twitter | https://boards.greenhouse.io/twitter",
        "Visa | https://visa.wd1.myworkdayjobs.com/Visa",
        "DP World | https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1",
    ]


def test_discover_verifies_oracle_seeds_with_real_adapter(monkeypatch):
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    monkeypatch.setattr(disc, "fetch_company_jobs", lambda c: [
        _jp("Software Engineer III", "Bengaluru, India", posted=RECENT)] if c.get("ats") == "oracle_hcm" else [])
    seeds = parse_seeds("DP World | https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1\n")
    verified, rows = disc.discover(seeds, workers=2)
    assert verified == [{"name": "DP World", "ats": "oracle_hcm", "host": "ehpv.fa.em2.oraclecloud.com",
                         "site": "CX_1", "headcount": "Unknown"}]


def test_merge_treats_oracle_boards_by_host_and_site():
    existing = [{"name": "DP World", "ats": "oracle_hcm", "host": "ehpv.fa.em2.oraclecloud.com", "site": "CX_1"}]
    new = [{"name": "JPMorgan Chase", "ats": "oracle_hcm", "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"},
           {"name": "DP World Logistics", "ats": "oracle_hcm", "host": "ehpv.fa.em2.oraclecloud.com", "site": "CX_1"},
           {"name": "Texas Instruments", "ats": "oracle_hcm", "host": "edbz.fa.us2.oraclecloud.com", "site": "CX_1"}]
    assert [c["name"] for c in merge_companies(existing, new)] == ["DP World", "JPMorgan Chase", "Texas Instruments"]


def test_reverify_existing_uses_real_adapter_for_amazon_and_oracle(monkeypatch):
    monkeypatch.setattr(disc, "fetch_company_jobs", lambda c: [_jp(posted=RECENT)])
    kept, rows = disc.reverify_existing([
        {"name": "Amazon", "ats": "amazon"},
        {"name": "DP World", "ats": "oracle_hcm", "host": "h.oraclecloud.com", "site": "CX_1"}])
    assert [c["name"] for c in kept] == ["Amazon", "DP World"]


def test_evidence_url_drops_json_escape_backslash():
    text = '{"link":"https:\\/\\/x"} <script>var u="https://jobs.lever.co/dreamsports\\";</script>'
    assert disc.evidence_url(text, "lever") == "https://jobs.lever.co/dreamsports"


@patch("requests.post")
def test_evaluate_workday_reads_the_location_like_the_adapter_does(mock_post):
    """T49: Accenture's list API has no locationsText (the city is in bulletFields), so discovery
    rejected it as 'no India jobs' although its India search returns 2,000 postings."""
    mock_post.return_value = _resp(payload={"jobPostings": [
        {"title": "Application Developer", "locationsText": "", "externalPath": "/job/Bengaluru-BDC4C/App-Dev_R1",
         "bulletFields": ["R1", "Bengaluru, Bdc4C"]},
        {"title": "Software Engineer", "locationsText": "", "externalPath": "/job/Hyderabad/SE_R2",
         "bulletFields": ["R2", "Hyderabad"]},
        {"title": "Software Engineer", "locationsText": "Austin", "externalPath": "/job/Austin/SE_R3"}]})
    row = disc.evaluate_workday("Accenture", "accenture", "wd103", "AccentureCareers")
    assert row["place_jobs"] == 2 and row["prefilter_pass"] == 2 and row["accepted"] is True


# --- T25: Eightfold boards (host + employer domain) ----------------------------------------

def test_parse_seeds_reads_eightfold_lines():
    seeds = parse_seeds("UKG | eightfold | apply.ukg.com | ukg.com\nMicron | eightfold | micron.eightfold.ai | micron.com\n")
    assert seeds[0] == {"name": "UKG", "eightfold": {"host": "apply.ukg.com", "domain": "ukg.com"}}
    assert seeds[1]["eightfold"] == {"host": "micron.eightfold.ai", "domain": "micron.com"}


def test_discover_verifies_eightfold_seeds_with_real_adapter_and_does_not_slug_probe(monkeypatch):
    from datetime import date
    asked = []

    def fake_fetch(c):
        asked.append(c.get("ats"))
        return [_jp("Software Engineer III", "Bengaluru, India", posted=date.today().isoformat())] if c.get("ats") == "eightfold" else []

    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    monkeypatch.setattr(disc, "fetch_company_jobs", fake_fetch)
    verified, rows = disc.discover(parse_seeds("UKG | eightfold | apply.ukg.com | ukg.com\n"), workers=2)
    assert verified == [{"name": "UKG", "ats": "eightfold", "host": "apply.ukg.com", "domain": "ukg.com", "headcount": "Unknown"}]
    assert set(asked) == {"eightfold"}                       # no greenhouse/lever/... slug guesses for an Eightfold seed


def test_merge_treats_eightfold_boards_by_host_and_domain():
    existing = [{"name": "UKG", "ats": "eightfold", "host": "apply.ukg.com", "domain": "ukg.com"}]
    new = [{"name": "Twilio", "ats": "eightfold", "host": "jobs.twilio.com", "domain": "twilio.com"},
           {"name": "Ultimate Kronos Group", "ats": "eightfold", "host": "apply.ukg.com", "domain": "ukg.com"}]
    assert [c["name"] for c in merge_companies(existing, new)] == ["Twilio", "UKG"]


def test_reverify_existing_uses_the_real_adapter_for_eightfold(monkeypatch):
    from datetime import date
    seen = []
    monkeypatch.setattr(disc, "fetch_company_jobs", lambda c: seen.append(c) or [_jp(posted=date.today().isoformat())])
    kept, _ = disc.reverify_existing([{"name": "UKG", "ats": "eightfold", "host": "apply.ukg.com", "domain": "ukg.com"}])
    assert [c["name"] for c in kept] == ["UKG"]
    assert seen[0]["host"] == "apply.ukg.com" and seen[0]["domain"] == "ukg.com"


# --- T26: Phenom boards (host + locale path) ------------------------------------------------

def test_parse_seeds_reads_phenom_lines():
    seeds = parse_seeds("BCG | phenom | careers.bcg.com | global/en\n")
    assert seeds == [{"name": "BCG", "phenom": {"host": "careers.bcg.com", "locale": "global/en"}}]


def test_discover_verifies_phenom_seeds_with_the_real_adapter_and_does_not_slug_probe(monkeypatch):
    from datetime import date
    asked = []

    def fake_fetch(c):
        asked.append(c.get("ats"))
        return [_jp("Senior Backend Engineer", "Bengaluru, India", posted=date.today().isoformat())] if c.get("ats") == "phenom" else []

    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    monkeypatch.setattr(disc, "fetch_company_jobs", fake_fetch)
    verified, rows = disc.discover(parse_seeds("BCG | phenom | careers.bcg.com | global/en\n"), workers=2)
    assert verified == [{"name": "BCG", "ats": "phenom", "host": "careers.bcg.com", "locale": "global/en", "headcount": "Unknown"}]
    assert set(asked) == {"phenom"}
    assert rows[0]["board"] == "careers.bcg.com:global/en"


def test_merge_treats_phenom_boards_by_host_and_locale():
    existing = [{"name": "BCG", "ats": "phenom", "host": "careers.bcg.com", "locale": "global/en"}]
    new = [{"name": "Boston Consulting Group", "ats": "phenom", "host": "careers.bcg.com", "locale": "global/en"},
           {"name": "Other", "ats": "phenom", "host": "careers.other.com", "locale": "us/en"}]
    assert [c["name"] for c in merge_companies(existing, new)] == ["BCG", "Other"]


def test_reverify_existing_uses_the_real_adapter_for_phenom(monkeypatch):
    from datetime import date
    seen = []
    monkeypatch.setattr(disc, "fetch_company_jobs", lambda c: seen.append(c) or [_jp(posted=date.today().isoformat())])
    kept, _ = disc.reverify_existing([{"name": "BCG", "ats": "phenom", "host": "careers.bcg.com", "locale": "global/en"}])
    assert [c["name"] for c in kept] == ["BCG"]
    assert seen[0]["host"] == "careers.bcg.com" and seen[0]["locale"] == "global/en"


@pytest.mark.parametrize("argv", [["--help"], ["-h"], ["--add-flie", "paste.txt", "--merge", "companies.json"]])
def test_main_never_starts_a_full_discovery_on_help_or_an_unknown_flag(argv, tmp_path, monkeypatch, capsys):
    """T67: unknown arguments were ignored, so `discover --help` or a mistyped flag ran discover() on every
    seed (~1,100 names, 40 workers, minutes of network) instead of printing usage."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "company_seeds.txt").write_text("Stripe\n")
    before = sorted(p.name for p in tmp_path.rglob("*"))
    monkeypatch.setattr(disc, "discover", lambda *a, **k: pytest.fail("a full discovery was started"))
    monkeypatch.setattr(disc, "recheck_companies", lambda *a, **k: pytest.fail("a recheck was started"))
    with pytest.raises(SystemExit) as ei:
        disc.main(argv)
    out = capsys.readouterr()
    if argv[0] in ("--help", "-h"):
        assert ei.value.code in (0, None) and "--add-file" in out.out
    else:
        assert ei.value.code not in (0, None) and "--add-flie" in str(ei.value.code) + out.err
    assert sorted(p.name for p in tmp_path.rglob("*")) == before   # nothing written


# -- T94: discover reads a LinkedIn headcount cache only when one is configured ------------------------------------------

def test_discover_reads_the_linkedin_cache_only_when_configured(monkeypatch):
    seen = []
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: seen.append(path) or ({}, {}))
    monkeypatch.setattr(disc, "fetch_company_jobs", lambda c: [])
    seeds = parse_seeds("DP World | https://ehpv.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1\n")
    monkeypatch.delenv("ROLESIGHT_LINKEDIN_CACHE", raising=False)
    disc.discover(seeds, workers=1)
    monkeypatch.setenv("ROLESIGHT_LINKEDIN_CACHE", "/data/li.json")
    disc.discover(seeds, workers=1)
    assert seen == ["", "/data/li.json"]


# ── T111: harvested boards ("Name | board URL | exact") ───────────────────────

def test_parse_seeds_reads_exact_board_lines_and_keeps_two_boards_of_one_name():
    seeds = parse_seeds("Acme | https://boards.greenhouse.io/acme | exact\nAcme | https://jobs.lever.co/acme | exact\n")
    assert [bool(s.get("exact")) for s in seeds] == [True, True]      # a plain name is deduped; two exact boards are two seeds
    assert [s["url"] for s in seeds] == ["https://boards.greenhouse.io/acme", "https://jobs.lever.co/acme"]


def test_an_exact_seed_probes_only_its_own_board_a_plain_one_also_guesses_the_name():
    exact, plain = parse_seeds("Acme Corp | https://boards.greenhouse.io/acme-corp | exact\n"
                               "Acme Corp 2 | https://boards.greenhouse.io/acme-corp\n")
    assert disc._probe_pairs(exact) == [("greenhouse", "acme-corp", True)]
    assert len(disc._probe_pairs(plain)) > 10                          # from the URL, then every slug guess on every ATS


def test_discover_checks_exact_seeds_at_their_own_board_and_names_them_from_the_board(monkeypatch):
    probed = []
    monkeypatch.setattr(disc, "_probe", lambda method, url, body, ats=None: probed.append(url) or (True, 200))
    monkeypatch.setattr(disc, "_board_name", lambda ats, slug: "\u200e Acme  Corporation\u200f " if (ats, slug) == ("greenhouse", "acme-corp") else None)
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    monkeypatch.setattr(disc, "evaluate_board", lambda name, ats, slug, from_url=False: {
        "seed": name, "accepted": True, "verdict": "verified", "ats": ats, "board": slug, "jobs": 5, "place_jobs": 2,
        "prefilter_pass": 1, "identity": "slug from company careers URL"})
    seeds = parse_seeds("Acme Corp | https://boards.greenhouse.io/acme-corp | exact\n"
                        "Acme Corp | https://jobs.lever.co/acme-corp | exact\n"
                        "Zed | https://jobs.ashbyhq.com/zed | exact\n")

    verified, rows = disc.discover(seeds, workers=2)

    assert len(probed) == 3                                            # one probe per seed, no slug guessing
    by_board = {(v["ats"], v["slug"]): v["name"] for v in verified}
    assert by_board == {("greenhouse", "acme-corp"): "Acme Corporation",   # the board's own name when it publishes one, spaces and invisible marks tidied
                        ("lever", "acme-corp"): "Acme Corp",               # otherwise the seed's
                        ("ashby", "zed"): "Zed"}
    assert len(rows) == 3                                              # each seed reports its own board only


def test_parse_seeds_keeps_every_exact_workday_site_of_a_tenant():
    seeds = parse_seeds("Acme | https://acme.wd1.myworkdayjobs.com/Careers | exact\nAcme | https://acme.wd1.myworkdayjobs.com/Campus | exact\n"
                        "Acme | https://acme.wd1.myworkdayjobs.com/Other\n")
    assert [s["workday"]["site"] for s in seeds] == ["Careers", "Campus", "Other"]   # a plain Acme line is its own seed, as before


def test_discover_puts_the_workday_site_with_most_place_jobs_first_so_the_merge_keeps_it(monkeypatch):
    india = {"Careers": 3, "Campus": 9, "Empty": 0}
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    monkeypatch.setattr(disc, "evaluate_workday", lambda name, tenant, dc, site: {
        "seed": name, "accepted": india[site] > 0, "verdict": "verified", "ats": "workday", "board": f"{tenant}.{dc}/{site}",
        "jobs": 20, "place_jobs": india[site], "prefilter_pass": 0,
        "entry": {"name": name, "ats": "workday", "tenant": tenant, "dc": dc, "site": site}})
    seeds = parse_seeds("".join(f"Acme | https://acme.wd1.myworkdayjobs.com/{s} | exact\n" for s in india))

    verified, rows = disc.discover(seeds, workers=2)

    assert [v["site"] for v in verified] == ["Campus", "Careers"]                    # busiest first; the empty site is not verified
    assert [r["board"].split("/")[1] for r in rows] == ["Careers", "Campus", "Empty"]   # the report keeps the seed order
    assert [c["site"] for c in merge_companies([], verified)] == ["Campus"]          # one entry per company


def test_discover_survives_a_board_that_makes_the_fetch_raise_and_reports_it(monkeypatch):
    """T111: one odd board (a null field in its jobs) used to end a 30-minute run; now it is one 'error' row."""
    monkeypatch.setattr(disc, "_probe", lambda method, url, body, ats=None: (True, 200))
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    monkeypatch.setattr(disc, "_board_name", lambda ats, slug: None)

    def fake_eval(name, ats, slug, from_url=False):
        if slug == "bad":
            raise AttributeError("'NoneType' object has no attribute 'strip'")
        return {"seed": name, "accepted": True, "verdict": "verified", "ats": ats, "board": slug, "jobs": 5, "place_jobs": 2,
                "prefilter_pass": 1, "identity": "slug from company careers URL"}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)

    def fake_workday(name, tenant, dc, site):
        if tenant == "boom":
            raise ValueError("bad payload")
        return {"seed": name, "accepted": True, "verdict": "verified", "ats": "workday", "board": tenant, "place_jobs": 1,
                "entry": {"name": name, "ats": "workday", "tenant": tenant, "dc": dc, "site": site}}
    monkeypatch.setattr(disc, "evaluate_workday", fake_workday)
    seeds = parse_seeds("Bad | https://boards.greenhouse.io/bad | exact\nGood | https://boards.greenhouse.io/good | exact\n"
                        "Boom | https://boom.wd1.myworkdayjobs.com/Site | exact\nFine | https://fine.wd1.myworkdayjobs.com/Site | exact\n")

    verified, rows = disc.discover(seeds, workers=2)

    assert sorted(v["name"] for v in verified) == ["Fine", "Good"]
    errors = {r["seed"]: r["verdict"] for r in rows if r["verdict"].startswith("error")}
    assert set(errors) == {"Bad", "Boom"}
    assert "AttributeError" in errors["Bad"] and "ValueError" in errors["Boom"]


def test_discover_survives_an_eightfold_or_phenom_site_that_makes_the_fetch_raise(monkeypatch):
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))

    def fake_fetch(company):
        if "boom" in company.get("host", ""):
            raise KeyError("positions")
        return [_jp(posted=date.today().isoformat(), location="Bengaluru, India")]
    monkeypatch.setattr(disc, "fetch_company_jobs", fake_fetch)
    seeds = parse_seeds("Fine EF | eightfold | fine.eightfold.ai | fine.com\nBoom EF | eightfold | boom.eightfold.ai | boom.com\n"
                        "Boom Phenom | phenom | boom.example.com | en_in\n")

    verified, rows = disc.discover(seeds, workers=2)

    assert [v["name"] for v in verified] == ["Fine EF"]
    errors = {r["seed"]: r["verdict"] for r in rows if r["verdict"].startswith("error")}
    assert set(errors) == {"Boom EF", "Boom Phenom"} and "KeyError" in errors["Boom EF"]


def test_workers_also_limits_how_many_boards_are_verified_at_once(monkeypatch):
    """T111: Workable and Recruitee answer HTTP 429 to 12 parallel fetches and the adapters read that as an empty board, so a
    gentle run (--workers 2) has to be gentle in the verification phase too, not only in the probe phase."""
    import threading
    import time
    monkeypatch.setattr(disc, "_probe", lambda method, url, body, ats=None: (True, 200))
    monkeypatch.setattr(disc, "_board_name", lambda ats, slug: None)
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    lock, state = threading.Lock(), {"now": 0, "max": 0}

    def fake_eval(name, ats, slug, from_url=False):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return {"seed": name, "accepted": False, "verdict": "no India jobs", "ats": ats, "board": slug}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)
    seeds = parse_seeds("".join(f"B{i} | https://jobs.lever.co/b{i} | exact\n" for i in range(12)))

    disc.discover(seeds, workers=2)

    assert state["max"] <= 2


# ── T111: the recheck must not read a rate limit as a dead board ──────────────

def test_the_recheck_spreads_entries_so_neighbours_rarely_share_an_ats():
    entries = [{"ats": "workable", "slug": f"w{i}"} for i in range(4)] + [{"ats": "lever", "slug": "l0"}, {"ats": "ashby", "slug": "a0"}]
    order = disc._spread_by_ats(entries)
    assert sorted(order) == list(range(6))                                           # every entry once
    assert [entries[i]["ats"] for i in order[:3]] == ["workable", "lever", "ashby"]  # one of each before the second workable


def test_reverify_gives_an_empty_answer_a_second_gentle_look_before_dropping_an_entry(monkeypatch):
    calls = []

    def fake_eval(name, ats, slug, from_url=False):
        calls.append(slug)
        first = calls.count(slug) == 1
        verdict = {"flaky": "no open jobs" if first else "verified", "dead": "no open jobs", "noindia": "no India jobs"}.get(slug, "verified")
        return {"seed": name, "accepted": verdict == "verified", "verdict": verdict, "ats": ats, "board": slug}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)
    entries = [{"name": n, "ats": "workable", "slug": n} for n in ("flaky", "dead", "noindia", "fine")]

    kept, rows = disc.reverify_existing(entries, workers=2)

    assert [c["name"] for c in kept] == ["flaky", "fine"]                            # flaky passed on the second look
    assert [r["verdict"] for r in rows] == ["verified", "no open jobs", "no India jobs", "verified"]   # rows stay in entry order
    assert calls.count("flaky") == 2 and calls.count("dead") == 2                    # an empty answer is asked twice
    assert calls.count("noindia") == 1 and calls.count("fine") == 1                  # a real answer is not


def test_reverify_second_look_uses_two_workers_at_most(monkeypatch):
    import threading
    import time
    lock = threading.Lock()
    state = {"seen": set(), "now": 0, "max": 0, "second_looks": 0}

    def fake_eval(name, ats, slug, from_url=False):
        with lock:
            second = slug in state["seen"]
            state["seen"].add(slug)
            if second:
                state["second_looks"] += 1
                state["now"] += 1
                state["max"] = max(state["max"], state["now"])
        time.sleep(0.03)
        if second:
            with lock:
                state["now"] -= 1
        return {"seed": name, "accepted": False, "verdict": "no open jobs", "ats": ats, "board": slug}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)

    disc.reverify_existing([{"name": f"b{i}", "ats": "workable", "slug": f"b{i}"} for i in range(10)], workers=8)

    assert state["second_looks"] == 10               # every empty answer was asked again ...
    assert state["max"] <= 2                         # ... gently, whatever --workers the first pass used


def test_reverify_submits_entries_spread_across_ats_not_in_sorted_order(monkeypatch):
    order = []

    def fake_eval(name, ats, slug, from_url=False):
        order.append(slug)
        return {"seed": name, "accepted": True, "verdict": "verified", "ats": ats, "board": slug}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)
    entries = [{"name": s, "ats": a, "slug": s} for a, s in      # as companies.json is sorted: the three Workable boards together
               [("workable", "w0"), ("workable", "w1"), ("workable", "w2"), ("lever", "l0"), ("ashby", "a0")]]

    disc.reverify_existing(entries, workers=1)                  # one worker: the call order is the submission order

    assert order == ["w0", "l0", "a0", "w1", "w2"]


def test_reverify_keeps_an_entry_whose_check_raises_and_says_so(monkeypatch):
    """A board that makes our fetch raise is not known to be dead; the monthly check must neither crash nor delete it."""
    def fake_eval(name, ats, slug, from_url=False):
        if slug == "odd":
            raise AttributeError("'NoneType' object has no attribute 'strip'")
        return {"seed": name, "accepted": slug != "gone", "verdict": "verified" if slug != "gone" else "no India jobs",
                "ats": ats, "board": slug}
    monkeypatch.setattr(disc, "evaluate_board", fake_eval)
    entries = [{"name": n, "ats": "greenhouse", "slug": n} for n in ("odd", "gone", "fine")]

    kept, rows = disc.reverify_existing(entries, workers=2)

    assert [c["name"] for c in kept] == ["odd", "fine"]
    assert rows[0]["verdict"].startswith("error") and "AttributeError" in rows[0]["verdict"] and rows[0]["accepted"] is True


# ── T113: the Workday light check resolves "N Locations" ─────────────────────────────────────────────────────────

def _wd_item(title, location, path):
    return {"title": title, "locationsText": location, "externalPath": path}


@patch("requests.post")
def test_workday_check_resolves_multi_location_postings_when_the_first_page_shows_no_india_job(mock_post, monkeypatch):
    """Northern Trust's India search has 99 hits but its first 20 read "2 Locations", "Chicago, IL", "Luxembourg": the real adapter
    resolves the placeholders with a detail call, the light check did not and flagged the board "no India jobs" (T113)."""
    mock_post.return_value = _resp(payload={"jobPostings": [
        _wd_item("Engineer", "2 Locations", "/job/a"), _wd_item("Analyst", "Chicago, IL", "/job/b"),
        _wd_item("Developer", "3 Locations", "/job/c"), _wd_item("Manager", "Location Negotiable", "/job/d")]})
    asked = []

    def fake_detail(cxs_base, external_path):
        asked.append((cxs_base, external_path))
        return {"/job/a": "Chicago, IL; Luxembourg", "/job/c": "London; Pune, India", "/job/d": "Austin"}[external_path]
    monkeypatch.setattr(disc, "fetch_detail_locations", fake_detail)

    row = disc.evaluate_workday("Northern Trust", "ntrs", "wd1", "northerntrust")

    assert row["accepted"] is True and row["place_jobs"] == 1
    assert [p for _, p in asked] == ["/job/a", "/job/c"]                      # stops at the first India job; "Chicago, IL" is not asked
    assert asked[0][0] == "https://ntrs.wd1.myworkdayjobs.com/wday/cxs/ntrs/northerntrust"
    assert row["prefilter_pass"] == 1                                          # the resolved location is what the filter sees: only "Developer" is in India


@patch("requests.post")
def test_workday_check_asks_for_at_most_eight_postings_and_then_says_no_place_jobs(mock_post, monkeypatch):
    mock_post.return_value = _resp(payload={"jobPostings": [_wd_item("Engineer", "2 Locations", f"/job/{i}") for i in range(20)]})
    asked = []
    monkeypatch.setattr(disc, "fetch_detail_locations", lambda base, path: asked.append(path) or "Chicago, IL; Luxembourg")

    row = disc.evaluate_workday("Acme", "acme", "wd1", "External")

    assert len(asked) == 8
    assert row["accepted"] is False and row["verdict"] == "no India jobs"


@patch("requests.post")
def test_workday_check_makes_no_detail_call_when_the_first_page_already_shows_an_india_job(mock_post, monkeypatch):
    mock_post.return_value = _resp(payload={"jobPostings": [_wd_item("Engineer", "Pune, India", "/job/1"),
                                                            _wd_item("Developer", "2 Locations", "/job/2")]})
    monkeypatch.setattr(disc, "fetch_detail_locations", lambda base, path: pytest.fail("a detail call was made"))
    assert disc.evaluate_workday("Acme", "acme", "wd1", "External")["accepted"] is True


@patch("requests.post")
def test_workday_check_survives_failed_detail_calls_and_postings_without_a_path(mock_post, monkeypatch):
    mock_post.return_value = _resp(payload={"jobPostings": [{"title": "Engineer", "locationsText": "2 Locations"},
                                                            _wd_item("Developer", "3 Locations", "/job/2")]})
    monkeypatch.setattr(disc, "fetch_detail_locations", lambda base, path: "")        # the adapter's answer when the call fails
    row = disc.evaluate_workday("Acme", "acme", "wd1", "External")
    assert row["accepted"] is False and row["place_jobs"] == 0


def _maintenance_response():
    """What Workday answers while a data centre is in maintenance: a 303 to community.workday.com, an HTML page, no JSON."""
    r = MagicMock()
    r.status_code = 200
    r.url = "https://community.workday.com/maintenance-page"
    r.history = [MagicMock(status_code=303)]
    r.headers = {"Content-Type": "text/html; charset=UTF-8"}
    r.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    return r


@patch("requests.post")
def test_workday_check_calls_a_maintenance_redirect_an_error_not_an_empty_board(mock_post):
    """wd102 was in maintenance on 2026-10-16: the light check read the HTML as 'no open jobs' for Hotstar, Minor, Piramal and Vena."""
    mock_post.return_value = _maintenance_response()
    row = disc.evaluate_workday("Hotstar", "jiostar", "wd102", "JioStar")
    assert row["accepted"] is False
    assert row["verdict"].startswith("error") and "community.workday.com/maintenance-page" in row["verdict"]
    assert "no open jobs" not in row["verdict"]


@patch("requests.post")
def test_the_recheck_keeps_a_workday_entry_while_its_data_centre_is_in_maintenance(mock_post):
    mock_post.return_value = _maintenance_response()
    entries = [{"name": "Hotstar", "ats": "workday", "tenant": "jiostar", "dc": "wd102", "site": "JioStar"}]
    kept, rows = disc.reverify_existing(entries, workers=1)
    assert [c["name"] for c in kept] == ["Hotstar"] and rows[0]["verdict"].startswith("error")


@patch("requests.post")
def test_workday_check_still_reads_a_redirect_that_ends_in_json(mock_post):
    """A tenant moved to another data centre answers with a redirect and then JSON: read as before (the adapter does the same)."""
    r = _resp(payload={"jobPostings": [{"title": "Software Engineer", "locationsText": "Pune, India"}]})
    r.url = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/External/jobs"
    r.history = [MagicMock(status_code=301)]
    r.headers = {"Content-Type": "application/json"}
    mock_post.return_value = r
    assert disc.evaluate_workday("Acme", "acme", "wd1", "External")["accepted"] is True



# ── T117: one entry per Oracle HCM host, the busiest site, named by its own title ────────────────────────────────

def _ora(name, host, site):
    return {"name": name, "ats": "oracle_hcm", "host": host, "site": site}


def test_merge_keeps_one_oracle_entry_per_host_the_first_given():
    existing = [_ora("Kotak Mahindra Bank", "hcbt.fa.em2.oraclecloud.com", "CX")]
    new = [_ora("Resideo", "ehtl.fa.us6.oraclecloud.com", "CX"), _ora("ADI", "ehtl.fa.us6.oraclecloud.com", "CX_2"),
           _ora("Kotak Additional", "hcbt.fa.em2.oraclecloud.com", "CX_1001"), _ora("Nokia", "fa-evmr.fa.ocs.oraclecloud.com", "CX_1")]
    assert [(c["name"], c["site"]) for c in merge_companies(existing, new)] == [
        ("Kotak Mahindra Bank", "CX"), ("Nokia", "CX_1"), ("Resideo", "CX")]


def test_oracle_hosts_are_compared_without_regard_to_case_and_other_ats_are_untouched():
    existing = [_ora("A", "HOST.fa.us2.oraclecloud.com", "CX")]
    new = [_ora("B", "host.fa.us2.oraclecloud.com", "CX_2"), {"name": "C", "ats": "greenhouse", "slug": "host"}]
    assert [c["name"] for c in merge_companies(existing, new)] == ["C", "A"]            # sorted by (ats, name)


def test_discover_then_merge_names_a_host_after_its_busiest_site_not_after_the_hosts_commonest_title(monkeypatch):
    """T117: Resideo's site has 7 India jobs, ADI's 1, and two sites are titled ADI: the entry must be Resideo."""
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))
    india = {"CX": 7, "CX_2": 1, "CX_3": 1}

    def fake_entry(name, entry):
        n = india[entry["site"]]
        return {"seed": name, "accepted": True, "verdict": "verified", "ats": "oracle_hcm", "board": f"{entry['host']}:{entry['site']}",
                "jobs": n, "place_jobs": n, "prefilter_pass": 0, "entry": {"name": name, **entry}}
    monkeypatch.setattr(disc, "evaluate_entry", fake_entry)
    host = "ehtl.fa.us6.oraclecloud.com"
    seeds = parse_seeds("".join(f"{n} | https://{host}/hcmUI/CandidateExperience/en/sites/{s} | exact\n"
                                for n, s in (("ADI", "CX_2"), ("ADI", "CX_3"), ("Resideo", "CX"))))
    verified, _ = disc.discover(seeds, workers=2)
    assert [c["name"] for c in merge_companies([], verified)] == ["Resideo"]


def test_discover_keeps_the_seed_order_on_a_tie_so_the_hosts_main_title_wins(monkeypatch):
    """T117 review: a host's sites can share their requisitions (7 sites with 23 India jobs each); the harvest writes the site with
    the host's main title first and discover must keep that order on a tie (a stable sort), not reorder by name."""
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))

    def fake_entry(name, entry):
        return {"seed": name, "accepted": True, "verdict": "verified", "ats": "oracle_hcm", "board": f"{entry['host']}:{entry['site']}",
                "jobs": 23, "place_jobs": 23, "prefilter_pass": 0, "entry": {"name": name, **entry}}
    monkeypatch.setattr(disc, "evaluate_entry", fake_entry)
    host = "mid.fa.em2.oraclecloud.com"
    # the main-title site sorts between the others by name, so a tie broken by name either way picks another site
    seeds = parse_seeds("".join(f"{n} | https://{host}/hcmUI/CandidateExperience/en/sites/{s} | exact\n"
                                for n, s in (("Mid Group", "CX"), ("Alpha Unit", "CX_2"), ("Zulu Unit", "CX_3"))))
    verified, _ = disc.discover(seeds, workers=3)
    assert [c["name"] for c in merge_companies([], verified)] == ["Mid Group"]


@pytest.mark.parametrize("content", ["", "\n\n", "# only a comment\n"])
def test_an_empty_add_file_stops_instead_of_checking_the_whole_seeds_file(tmp_path, monkeypatch, capsys, content):
    """T132: a census that found no board writes an empty seeds file; `--add-file` with it used to fall back to every line
    of scripts/company_seeds.txt (1,491 names, hours of network), because an empty paste read like "no --add-file given"."""
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Stripe\nPlane\n")
    add = tmp_path / "empty.txt"
    add.write_text(content)
    called = []
    monkeypatch.setattr(disc, "discover", lambda s, workers=40: called.append(s) or ([], []))
    with pytest.raises(SystemExit) as stop:
        disc.main(["--seeds", str(seeds), "--add-file", str(add), "--out", str(tmp_path / "v.json"), "--report", str(tmp_path / "r.csv")])
    assert stop.value.code not in (0, None)
    assert called == []                                                   # nothing was checked
    assert "no company" in str(stop.value.code).lower()
    assert seeds.read_text() == "Stripe\nPlane\n"                          # the seeds file is untouched
    assert not (tmp_path / "v.json").exists()


def test_without_add_options_the_seeds_file_is_still_checked(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Stripe\nPlane\n")
    seen = {}
    monkeypatch.setattr(disc, "discover", lambda s, workers=40: seen.setdefault("names", [x["name"] for x in s]) and ([], []))
    disc.main(["--seeds", str(seeds), "--out", str(tmp_path / "v.json"), "--report", str(tmp_path / "r.csv")])
    assert seen["names"] == ["Stripe", "Plane"]


@pytest.mark.parametrize("argv", [["--add", ","], ["--add", " "], ["--add", "# a note"], ["--add", ""], ["--add-file", ""]])
def test_an_add_option_with_no_company_name_stops_too(tmp_path, monkeypatch, argv):
    """T132 review: the same stop for `--add`, and for an explicitly empty value (a script's `--add "$NAMES"`
    with an empty variable), which `bool(opts[...])` read as "no --add given"."""
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Stripe\nPlane\n")
    called = []
    monkeypatch.setattr(disc, "discover", lambda s, workers=40: called.append(s) or ([], []))
    with pytest.raises(SystemExit) as stop:
        disc.main(["--seeds", str(seeds), *argv, "--out", str(tmp_path / "v.json"), "--report", str(tmp_path / "r.csv")])
    assert stop.value.code not in (0, None) and "no company" in str(stop.value.code).lower()
    assert called == [] and seeds.read_text() == "Stripe\nPlane\n"


# ── T155: discover must never read a refused or failed request as "no board" ────

def test_probe_refusal_or_failure_is_not_checked_never_no_board(monkeypatch):
    """T155: a Workable 429 -> not checked: HTTP 429 ...; 404 -> no live board; 200 (0 jobs) -> no live board."""
    def mock_probe(method, url, body=None, timeout=None, ats=None):
        if "throttled" in url:
            return False, 429
        if "missing" in url:
            return False, 404
        if "empty" in url:
            return False, "200 (0 jobs)"
        return True, 200

    import job_hunt.discovery as d
    monkeypatch.setattr(d, "_probe", mock_probe)

    # 1. 429 probe -> not checked: HTTP 429 ...
    _, rows = d.discover([{"name": "Throttled", "exact": True, "url": "https://apply.workable.com/throttled"}])
    assert len(rows) == 1
    assert rows[0]["verdict"].startswith("not checked: HTTP 429")
    assert rows[0]["accepted"] is False

    # 2. 404 probe -> no live board on supported ATSs
    _, rows = d.discover([{"name": "Missing", "exact": True, "url": "https://apply.workable.com/missing"}])
    assert len(rows) == 1
    assert rows[0]["verdict"] == "no live board on supported ATSs"
    assert rows[0]["accepted"] is False

    # 3. 200 with 0 jobs -> no live board on supported ATSs
    _, rows = d.discover([{"name": "Empty", "exact": True, "url": "https://apply.workable.com/empty"}])
    assert len(rows) == 1
    assert rows[0]["verdict"] == "no live board on supported ATSs"
    assert rows[0]["accepted"] is False


def test_discover_merge_keeps_existing_entry_on_429_or_503(tmp_path, monkeypatch):
    """T155: An existing entry answering 429 (Workable) or 503 (Greenhouse) through discover --merge stays in companies.json."""
    import job_hunt.discovery as d
    from job_hunt.adapters import base

    target = tmp_path / "companies.json"
    initial = [
        {"name": "ThrottledCo", "ats": "workable", "slug": "throttled"},
        {"name": "BrokenCo", "ats": "greenhouse", "slug": "broken"},
    ]
    target.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def fake_fetch(c):
        if c.get("slug") == "throttled":
            base.mark_incomplete("HTTP 429 from Workable (rate limited)")
            return []
        if c.get("slug") == "broken":
            base.mark_incomplete("HTTP 503")
            return []
        return []

    monkeypatch.setattr(d, "fetch_company_jobs", fake_fetch)

    empty_seeds = tmp_path / "seeds.txt"
    empty_seeds.write_text("", encoding="utf-8")
    out = tmp_path / "v.json"
    report = tmp_path / "report.csv"

    d.main(["--seeds", str(empty_seeds), "--merge", str(target), "--out", str(out), "--report", str(report)])

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert {c["name"] for c in saved} == {"ThrottledCo", "BrokenCo"}

    # Check report rows
    import csv
    with open(report, encoding="utf-8") as f:
        report_rows = list(csv.DictReader(f))
    verdicts = {r["seed"]: r["verdict"] for r in report_rows}
    assert "[existing] ThrottledCo" in verdicts
    assert verdicts["[existing] ThrottledCo"].startswith("not checked")
    assert "[existing] BrokenCo" in verdicts
    assert verdicts["[existing] BrokenCo"].startswith("not checked")


def test_recheck_companies_neither_removes_nor_replaces_not_checked_entry(monkeypatch):
    """T155: discover --recheck neither removes nor replaces an entry that answers not checked."""
    import job_hunt.discovery as d
    from job_hunt.adapters import base

    entries = [{"name": "ThrottledCo", "ats": "workable", "slug": "throttled"}]

    def fake_fetch(c):
        base.mark_incomplete("HTTP 429 from Workable (rate limited)")
        return []

    monkeypatch.setattr(d, "fetch_company_jobs", fake_fetch)

    updated, report_rows = d.recheck_companies(entries)
    assert [c["name"] for c in updated] == ["ThrottledCo"]
    assert not any("REMOVED" in r.get("verdict", "") or "REPLACED" in r.get("verdict", "") for r in report_rows)
    assert any(r.get("verdict", "").startswith("not checked") for r in report_rows)


# ── T156: Name collisions when merging new companies ─────────────────────────

def test_name_collisions_phoenix_software_against_phoenix():
    """T156: 'Phoenix Software' (workable) against existing 'Phoenix' (oracle_hcm) -> not added, reported with both boards."""
    from job_hunt import discovery as d
    existing = [{"name": "Phoenix", "ats": "oracle_hcm", "host": "egeg.fa.em3.oraclecloud.com", "site": "CX_1"}]
    new = [{"name": "Phoenix Software", "ats": "workable", "slug": "phoenix-software"}]

    cols = d.name_collisions(existing, new)
    assert len(cols) == 1
    assert cols[0]["seed"] == "Phoenix Software"
    assert cols[0]["ats"] == "workable"
    assert cols[0]["board"] == "phoenix-software"
    assert cols[0]["verdict"] == "name collision: not added; existing Phoenix (oracle_hcm/egeg.fa.em3.oraclecloud.com:CX_1)"

    merged = d.merge_companies(existing, new)
    assert [c["name"] for c in merged] == ["Phoenix"]


def test_name_collisions_mindtickle_india_against_mindtickle():
    """T156: 'Mindtickle India' against 'Mindtickle' -> reported too."""
    from job_hunt import discovery as d
    existing = [{"name": "Mindtickle", "ats": "greenhouse", "slug": "mindtickle"}]
    new = [{"name": "Mindtickle India", "ats": "lever", "slug": "mindtickle-india"}]

    cols = d.name_collisions(existing, new)
    assert len(cols) == 1
    assert cols[0]["seed"] == "Mindtickle India"
    assert cols[0]["ats"] == "lever"
    assert cols[0]["board"] == "mindtickle-india"
    assert cols[0]["verdict"] == "name collision: not added; existing Mindtickle (greenhouse/mindtickle)"

    merged = d.merge_companies(existing, new)
    assert [c["name"] for c in merged] == ["Mindtickle"]


def test_name_collisions_same_board_twice_stays_silent():
    """T156: The same board twice -> silent, as today."""
    from job_hunt import discovery as d
    existing = [{"name": "Stripe", "ats": "greenhouse", "slug": "stripe"}]
    new = [
        {"name": "Stripe", "ats": "greenhouse", "slug": "stripe"},
        {"name": "Stripe Duplicate", "ats": "greenhouse", "slug": "stripe"},
    ]

    cols = d.name_collisions(existing, new)
    assert cols == []


def test_name_collisions_t160_replay_fixture():
    """T156: Replaying T160 drops drops exactly Intertek and Phoenix Software as name collisions."""
    from job_hunt import discovery as d
    existing = [
        {"name": "Intertek", "ats": "oracle_hcm", "host": "hcog.fa.em2.oraclecloud.com", "site": "CX_2001"},
        {"name": "Phoenix", "ats": "oracle_hcm", "host": "egeg.fa.em3.oraclecloud.com", "site": "CX_1"},
        {"name": "OtherCo", "ats": "greenhouse", "slug": "otherco"},
    ]
    new = [
        {"name": "Intertek", "ats": "workable", "slug": "intertek"},
        {"name": "Phoenix Software", "ats": "workable", "slug": "phoenix-software"},
        {"name": "FreshCo", "ats": "workable", "slug": "freshco"},
    ]

    cols = d.name_collisions(existing, new)
    assert len(cols) == 2
    assert {c["seed"] for c in cols} == {"Intertek", "Phoenix Software"}
    assert cols[0]["verdict"] == "name collision: not added; existing Intertek (oracle_hcm/hcog.fa.em2.oraclecloud.com:CX_2001)"
    assert cols[1]["verdict"] == "name collision: not added; existing Phoenix (oracle_hcm/egeg.fa.em3.oraclecloud.com:CX_1)"

    merged = d.merge_companies(existing, new)
    assert {c["name"] for c in merged} == {"Intertek", "Phoenix", "OtherCo", "FreshCo"}


def test_merge_into_todays_list_keeps_both_phoenix_and_both_target_entries():
    """T156: A merge into today's list keeps both Phoenix entries and both Target entries."""
    from pathlib import Path

    from job_hunt import discovery as d
    target_path = Path("companies.json")
    if not target_path.exists():
        pytest.skip("companies.json not found")
    today_list = json.loads(target_path.read_text(encoding="utf-8"))

    phoenix_initial = [c["name"] for c in today_list if "phoenix" in c["name"].lower()]
    target_initial = [c["name"] for c in today_list if "target" in c["name"].lower()]
    assert set(phoenix_initial) == {"Phoenix", "Phoenix Software"}
    assert set(target_initial) == {"Target Group", "Target India"}

    merged = d.merge_companies(today_list, [])
    assert {c["name"] for c in merged if "phoenix" in c["name"].lower()} == {"Phoenix", "Phoenix Software"}
    assert {c["name"] for c in merged if "target" in c["name"].lower()} == {"Target Group", "Target India"}


def test_discover_merge_reports_name_collision_in_stdout_and_report_file(tmp_path, monkeypatch, capsys):
    """T156: discover --merge prints the collision naming both boards and writes report row."""
    from job_hunt import discovery as d

    target = tmp_path / "companies.json"
    target.write_text(json.dumps([
        {"name": "Phoenix", "ats": "oracle_hcm", "host": "egeg.fa.em3.oraclecloud.com", "site": "CX_1"},
    ], indent=2), encoding="utf-8")

    seeds = tmp_path / "seeds.txt"
    seeds.write_text("Phoenix Software\n", encoding="utf-8")
    out = tmp_path / "out.json"
    report = tmp_path / "report.csv"

    def fake_discover(seeds, workers=40):
        verified = [{"name": "Phoenix Software", "ats": "workable", "slug": "phoenix-software", "headcount": "Unknown"}]
        rows = [{"seed": "Phoenix Software", "verdict": "verified", "ats": "workable", "board": "phoenix-software"}]
        return verified, rows

    monkeypatch.setattr(d, "discover", fake_discover)

    d.main(["--seeds", str(seeds), "--merge", str(target), "--out", str(out), "--report", str(report), "--no-recheck"])

    captured = capsys.readouterr().out
    assert "name collision: Phoenix Software (workable/phoenix-software) not added; existing Phoenix (oracle_hcm/egeg.fa.em3.oraclecloud.com:CX_1)" in captured

    # Existing was not modified/replaced
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert [c["name"] for c in saved] == ["Phoenix"]

    # Report has collision row
    import csv
    with open(report, encoding="utf-8") as f:
        report_rows = list(csv.DictReader(f))
    collision_row = next((r for r in report_rows if r["seed"] == "Phoenix Software" and "name collision" in r["verdict"]), None)
    assert collision_row is not None
    assert collision_row["verdict"] == "name collision: not added; existing Phoenix (oracle_hcm/egeg.fa.em3.oraclecloud.com:CX_1)"
    assert collision_row["ats"] == "workable"
    assert collision_row["board"] == "phoenix-software"



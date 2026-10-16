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


# ── T112: Oracle HCM candidate sites carry no company name in their host; the page title does ─────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("Hilton", "Hilton"), ("Sherwin-Williams", "Sherwin-Williams"), ("Yum!", "Yum!"), ("T.EN Career Site", "T.EN"),
    ("APS External Career Site", "APS"), ("BDO USA Campus Career Site", "BDO USA Campus"), ("Hoya Global Career Site", "Hoya"),
    ("Nexi Career Site", "Nexi"), ("PNI Careers", "PNI"), ("KFH Careers", "KFH"), ("RBKC Careers", "RBKC"),
    ("Green Climate Fund Jobs", "Green Climate Fund"), ("ENBD Recruitment Team", "ENBD"), ("Emirate Islamic Bank Recruitment Team", "Emirate Islamic Bank"),
    ("ELCA Global Career site", "ELCA"), ("COOPENAE Candidate Experience site", "COOPENAE"),
    ("St. Joseph\\'s Health", "St. Joseph's Health"), ("Connecticut Children\\'s", "Connecticut Children's"),
    ("Careers at Acme Corp", "Acme Corp"), ("Jobs at Acme", "Acme"), ("  Acme   Corp  ", "Acme Corp"), ("Acme &amp; Sons Careers", "Acme & Sons"),
    ("Acme | Careers", "Acme"), ("Acme - Career Site", "Acme"), ("AWR Career Site", "AWR"), ("SELA WEBSITE", "SELA"), ("Acme Careers - Jobs", "Acme"), ("Acme Career Site | Careers", "Acme"),
    # a page title is often "<something generic> | <the employer>" or the other way round: the first part that names someone
    ("Careers | BXP", "BXP"), ("Job Opportunities | MCB Group", "MCB Group"), ("Job Search | Gulf Bank", "Gulf Bank"),
    ("Meezan Bank - Careers | Job Opportunities | Islamic Banking", "Meezan Bank"),
    ("New River Valley Community Services | Careers Center", "New River Valley Community Services"),
    ("Sherwin-Williams", "Sherwin-Williams"), ("Acme \u2013 Open Positions", "Acme"),
    ("ACI Worldwide Job Opportunities", "ACI Worldwide"), ("Cummins Talent Acquisition", "Cummins"), ("Careers @ MUFG Pension & Market Services", "MUFG Pension & Market Services"),
    ("Career Site(Servify)", "Servify"), ("Career Site (Acme)", "Acme"),
    ("Opportunit\u00e9s au sein du Groupe Legrand", "Legrand"), ("Sua carreira na Cyncly", "Cyncly"),
    ("Site carri\u00e8re externe sodiaal", "sodiaal"), ("Site Carri\u00e8re Savencia", "Savencia"),
    ("Careers|BXP", "BXP"), ("Careers Center | Acme", "Acme"), ("Career Center - Acme", "Acme"), ("Join Us | Acme", "Acme"),
    ("\\u0645\\u0648\\u0628\\u0627\\u064A\\u0644\\u064A", "\u0645\u0648\u0628\u0627\u064a\u0644\u064a"),    # JSON-escaped text (Mobily) is decoded
    ("Site Carri\\u00E8re Savencia", "Savencia"),
])
def test_an_oracle_site_title_becomes_the_employers_name(raw, expected):
    assert hb.clean_site_title(raw) == expected


@pytest.mark.parametrize("raw", [
    "", None, "Page not found", "Service Unavailable", "Subscription Suspension Outage", "Candidate Experience site", "Candidate Experience-Site",
    "Candidate Experience Spain", "Careers", "Career Site", "Jobs", "Oracle Recruiting Cloud", "Home", "External", "Website",
    "HR", "Human Resources", "Americas Career Opportunities", "EMEA Careers", "Global Careers",
    "Aerospace", "Defense", "Healthcare", "Banking", "Logistics", "Energy Careers", "\u5019\u88dc\u8005\u30a8\u30af\u30b9\u30da\u30ea\u30a8\u30f3\u30b9\u30fb\u30b5\u30a4\u30c8", "\u5019\u9009\u4eba\u5de5\u4f5c\u7ecf\u9a8c\u7ad9\u70b9",
])
def test_a_title_that_names_no_employer_gives_no_name(raw):
    assert hb.clean_site_title(raw) == ""


def test_an_oracle_site_is_a_seed_only_with_a_name_and_not_for_a_test_or_dev_instance():
    urls = ["https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1",
            "https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2",
            "https://nameless.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX",
            "https://rbkc-iagrme-dev1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/RBKC",
            "https://fa-enfw-test-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_4003",
            "https://egue-dev12.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/fr/sites/CX_42004"]
    names = {"hdjq.fa.us2.oraclecloud.com:CX_1": "Acme Corp", "hdjq.fa.us2.oraclecloud.com:CX_2": "Acme Corp",
             "rbkc-iagrme-dev1.fa.ocs.oraclecloud.com:RBKC": "RBKC", "fa-enfw-test-saasfaprod1.fa.ocs.oraclecloud.com:CX_4003": "Dos Pinos",
             "egue-dev12.fa.us2.oraclecloud.com:CX_42004": "InVision"}
    lines = hb.board_seeds(urls, [], names=names)
    assert lines == ["Acme Corp | https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1 | exact",
                     "Acme Corp | https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2 | exact"]
    seeds = parse_seeds("\n".join(lines))
    assert len(seeds) == 2 and all("oracle_hcm" in x for x in seeds)          # discover reads them as Oracle seeds; both sites are kept


def test_an_oracle_site_already_in_companies_json_is_skipped():
    existing = [{"name": "National Instruments", "ats": "oracle_hcm", "host": "hdjq.fa.us2.oraclecloud.com", "site": "CX_1"}]
    urls = ["https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1"]
    assert hb.board_seeds(urls, existing, names={"hdjq.fa.us2.oraclecloud.com:CX_1": "National Instruments"}) == []


class _Page:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


class _Pages:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def get(self, url, **kw):
        self.asked.append(url)
        answer = self.answers.get(url)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_site_names_are_read_from_the_page_title_and_a_failed_page_gives_no_name():
    base = "https://{}/hcmUI/CandidateExperience/en/sites/{}"
    pages = _Pages({base.format("a.fa.us2.oraclecloud.com", "CX"): _Page(200, "<html><head><TITLE>Hilton Careers</TITLE></head></html>"),
                    base.format("b.fa.us2.oraclecloud.com", "CX"): _Page(403, "<html><head><title>Acme</title></head></html>"),
                    base.format("c.fa.us2.oraclecloud.com", "CX"): RuntimeError("timeout"),
                    base.format("d.fa.us2.oraclecloud.com", "CX"): _Page(200, "<html><head><title>Page not found</title></head></html>")})
    got = hb.fetch_site_names([base.format(f"{h}.fa.us2.oraclecloud.com", "CX") for h in "abcd"], session=pages, workers=1)
    assert got == {"a.fa.us2.oraclecloud.com:CX": "Hilton"}


def test_main_names_the_oracle_sites_from_their_pages_and_writes_them_as_seeds(tmp_path, monkeypatch, capsys):
    site = "https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1"
    nameless = "https://zzzz.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX"
    monkeypatch.setattr(hb, "fetch_urls", lambda query, session=None: [site, nameless] if query["name"] == "oracle-us2" else [])
    seen = []
    monkeypatch.setattr(hb, "fetch_site_names", lambda urls, **kw: seen.append(list(urls)) or {"hdjq.fa.us2.oraclecloud.com:CX_1": "Acme Corp"})
    out = tmp_path / "seeds.txt"
    assert hb.main(["--out", str(out), "--hosts", "oracle-us2", "--companies", str(tmp_path / "none.json")]) == 0
    assert out.read_text().splitlines() == [f"Acme Corp | {site} | exact"]
    assert seen == [[site, nameless]]
    assert "oracle: 1 of 2 site(s) name an employer" in capsys.readouterr().out


def test_main_carries_on_when_the_archive_does_not_answer_for_one_host_and_says_which(tmp_path, monkeypatch, capsys):
    """T112: the archive failed one of 13 queries three times and the run ended with nothing written."""
    def fetch(query, session=None):
        if query["name"] == "lever":
            raise RuntimeError("the Internet Archive did not answer for lever after 3 tries")
        return ["https://jobs.ashbyhq.com/plane"]
    monkeypatch.setattr(hb, "fetch_urls", fetch)
    out = tmp_path / "seeds.txt"
    code = hb.main(["--out", str(out), "--hosts", "lever,ashby", "--companies", str(tmp_path / "none.json")])
    assert code == 3                                                       # partial: the seeds are written, the caller is told
    assert out.read_text().splitlines() == ["Plane | https://jobs.ashbyhq.com/plane | exact"]
    captured = capsys.readouterr()
    assert "lever" in captured.err and "ashby" not in captured.err.split("did not answer")[-1] and "1 seed" in captured.out


# ── T112: on Oracle HCM the host is the employer; its sites are its career sites ───────────────────────────────────────

def _oracle(host, site):
    return f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}"


def test_all_the_sites_of_one_oracle_host_carry_the_employers_most_common_title_as_their_name():
    host = "ehpv.fa.em2.oraclecloud.com"
    urls = [_oracle(host, s) for s in ("CX", "CX_1", "WeOneCareers")]
    names = {f"{host}:CX": "DP World", f"{host}:CX_1": "DP World", f"{host}:WeOneCareers": "We One"}
    assert hb.board_seeds(urls, [], names=names) == [f"DP World | {u} | exact" for u in sorted(urls)]


def test_a_tie_between_titles_goes_to_the_shorter_name_then_the_alphabetical_one():
    host = "abcd.fa.us2.oraclecloud.com"
    urls = [_oracle(host, "CX_1"), _oracle(host, "CX_2")]
    assert hb.board_seeds(urls, [], names={f"{host}:CX_1": "Acme Alumni", f"{host}:CX_2": "Acme"})[0].startswith("Acme | ")
    assert hb.board_seeds(urls, [], names={f"{host}:CX_1": "Beta", f"{host}:CX_2": "Alfa"})[0].startswith("Alfa | ")


def test_an_oracle_host_that_is_already_in_companies_json_is_skipped_whatever_the_site():
    existing = [{"name": "Kotak Mahindra Bank", "ats": "oracle_hcm", "host": "hcbt.fa.em2.oraclecloud.com", "site": "CX"}]
    urls = [_oracle("hcbt.fa.em2.oraclecloud.com", "CX_1001"), _oracle("other.fa.em2.oraclecloud.com", "CX")]
    names = {"hcbt.fa.em2.oraclecloud.com:CX_1001": "Kotak Additional", "other.fa.em2.oraclecloud.com:CX": "Other Co"}
    assert hb.board_seeds(urls, existing, names=names) == [f"Other Co | {_oracle('other.fa.em2.oraclecloud.com', 'CX')} | exact"]


def test_hosts_are_compared_without_regard_to_case():
    existing = [{"name": "X", "ats": "oracle_hcm", "host": "HCBT.fa.em2.oraclecloud.com", "site": "CX"}]
    assert hb.board_seeds([_oracle("hcbt.fa.em2.oraclecloud.com", "CX_2")], existing, names={"hcbt.fa.em2.oraclecloud.com:CX_2": "Kotak"}) == []


def test_an_oracle_site_whose_own_title_names_nobody_takes_its_hosts_name():
    host = "abcd.fa.us2.oraclecloud.com"
    urls = [_oracle(host, "CX"), _oracle(host, "CX_2")]
    lines = hb.board_seeds(urls, [], names={f"{host}:CX": "Acme"})              # CX_2's page said "Page not found"
    assert lines == [f"Acme | {u} | exact" for u in urls]


def test_a_name_never_carries_the_seed_separator():
    host = "abcd.fa.us2.oraclecloud.com"
    lines = hb.board_seeds([_oracle(host, "CX")], [], names={f"{host}:CX": "Acme | Corp"})
    assert len(lines) == 1 and lines[0].count("|") == 2 and lines[0].startswith("Acme / Corp | ")
    assert len(parse_seeds(lines[0])) == 1

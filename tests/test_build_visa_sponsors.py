"""T133: scripts/build_visa_sponsors.py — name matching, the source parsers, the review file and the build (no network)."""
import importlib.util
import json
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("bvs", ROOT / "scripts" / "build_visa_sponsors.py")
bvs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bvs)


@pytest.mark.parametrize("name, exact, loose", [
    ("Google (UK) Limited", "google", "google"),
    ("Atlassian (UK) Operations Limited", "atlassian operations", "atlassian"),
    ("Booking.com B.V.", "booking", "booking"),
    ("Adyen N.V.", "adyen", "adyen"),
    ("Schrödinger Technologies Limited", "schrodinger technologies", "schrodinger"),
    ("DBS Bank Ltd, London Branch", "dbs bank", "dbs"),          # a branch's place goes
    ("Amazon EU SARL, Dutch Branch", "amazon", "amazon"),
    ("BRAVE LONDON LTD", "brave london", "brave london"),         # a city alone stays: "Brave London Ltd" is not Brave
    ("Stripe Partners", "stripe partners", "stripe partners"),
    # the H-1B file's ways (T143): a trade name after "D B A", letters spaced out, US suffixes
    ("ANTHROPIC PBC D B A ANTHROPIC INC", "anthropic", "anthropic"), ("RAINTANK INC DBA GRAFANA LABS", "grafana labs", "grafana"),
    ("OPENAI L L C", "openai", "openai"), ("OPENAI OPCO LLC", "openai", "openai"), ("ADYEN N V", "adyen", "adyen"),
    ("DBA LIMITED", "dba", "dba"),                                # a name that is only "DBA" keeps it
    ("Google Canada Corporation", "google", "google"),
])
def test_name_keys(name, exact, loose):
    assert bvs.exact_key(name) == exact
    assert bvs.loose_key(name) == loose


def test_match_prefers_exact_and_never_matches_another_business_with_the_same_first_word():
    idx = bvs.Index({"Stripe Payments UK Ltd": [], "Stripe Partners": [], "STRIPE CONSULTING LIMITED": [],
                     "Amazon UK Services Ltd": [], "Amazon Filters Ltd": [], "Amazon Charitable Trust": [],
                     "Keller Postman UK Limited": [], "Google (UK) Limited": [], "Google Services Ltd": []})
    assert idx.match("Stripe") == ("loose", ["Stripe Payments UK Ltd"])
    assert idx.match("Amazon") == ("loose", ["Amazon UK Services Ltd"])
    assert idx.match("Google") == ("exact", ["Google (UK) Limited"])     # the loose "Google Services Ltd" is not added
    assert idx.match("Postman") == (None, [])
    assert idx.match("") == (None, [])


def test_parse_uk_keeps_the_worker_routes_and_strips_the_names(tmp_path):
    p = tmp_path / "uk.csv"
    p.write_text("Organisation Name,Town/City,County,Type & Rating,Route\n"
                 " Acme Limited,London,,Worker (A rating),Skilled Worker\n"
                 "Acme Limited,London,,Worker (A rating),Global Business Mobility: Senior or Specialist Worker\n"
                 "Church Of Acme,Leeds,,Worker (A rating),Tier 2 Ministers of Religion\n", encoding="utf-8")
    assert bvs.parse_uk(p) == {"Acme Limited": ["Global Business Mobility: Senior or Specialist Worker", "Skilled Worker"]}


def test_parse_nl_reads_the_row_header_cell_and_skips_the_table_header():
    page = ('<table><tr><th>Organisation</th><th>KVK (Chamber of Commerce) number</th></tr>'
            '<tr><th scope="row">""Aa-Dee"" Machinefabriek B.V.</th><td>16051874</td></tr>'
            '<tr><th scope="row">Adyen N.V.</th><td>34259528</td></tr></table>')
    assert bvs.parse_nl(page) == {'"Aa-Dee" Machinefabriek B.V.': "16051874", "Adyen N.V.": "34259528"}


def _xlsx(path, rows):
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(path)


def test_parse_ie_reads_both_yearly_layouts(tmp_path):
    _xlsx(tmp_path / "2025.xlsx", [(None, "January", "February", "Grand Total"), ("Grand Total", 5, 7, 12),
                                   (" IQVIA RDS IRELAND LTD", None, 1, 1), ("Stripe Payments Europe Limited", 3, 8, 11)])
    _xlsx(tmp_path / "2026.xlsx", [("Employer Name", "Permits Issued Jan", "Permits Issued Grand Total"),
                                   ("Stripe Payments Europe Limited", 2, 2), ("Total", 2, 2)])
    assert bvs.parse_ie(tmp_path / "2025.xlsx") == {"IQVIA RDS IRELAND LTD": 1, "Stripe Payments Europe Limited": 11}
    assert bvs.parse_ie(tmp_path / "2026.xlsx") == {"Stripe Payments Europe Limited": 2}


GIST = json.dumps({"files": {"list.md": {"content": "Intro text\n\n**London**\n* [Google](https://careers.google.com/)\n"
                                                     "* [Monzo](https://monzo.com)\n\n**Berlin, Germany**\n* [Google](x)\n"
                                                     "* [Zalando](https://jobs.zalando.com)\n"}}})
SHUBHEKSHA = ("| Name  | Location(s)  |Roles sponsored  |  Careers page |\n|-------|--------------|----|----|\n"
              "| Stripe| London, UK <br>Dublin, IE| Engineering| https://stripe.com/jobs|\n"
              "| QuantumBlack | [Global](https://quantumblack.com/careers) | Data | x |\n")


def test_parse_the_community_lists():
    assert bvs.parse_gist(GIST) == {"Google": ["London", "Berlin, Germany"], "Monzo": ["London"], "Zalando": ["Berlin, Germany"]}
    assert bvs.parse_shubheksha(SHUBHEKSHA) == {"Stripe": ["London, UK", "Dublin, IE"], "QuantumBlack": ["Global"]}


def test_status_keeps_exact_matches_and_only_accepted_loose_ones():
    review = {"accepted": {"Stripe": ["Stripe Payments UK Ltd"]}, "rejected": {"Phoenix": ["Phoenix Software Limited"]}}
    assert bvs.status("Stripe", "Stripe Payments UK Ltd", "loose", review) == "kept"
    assert bvs.status("Canva", "CANVA UK OPERATIONS LIMITED", "loose", review) == "unreviewed"
    assert bvs.status("Revolut", "Revolut Ltd", "exact", review) == "kept"
    assert bvs.status("Phoenix", "Phoenix Software Limited", "exact", review) == "rejected"   # rejected wins over exact


def test_an_exact_match_on_a_name_of_five_letters_or_fewer_counts_only_when_accepted():
    """T144 review: "River" matched a hospital's trade name and "UK-Med" (the country word goes, "med" is left) a software
    firm's; a key that short names many businesses, as squashed_key's six-letter floor already says."""
    review = {"accepted": {"Adyen": ["Adyen N.V."]}, "rejected": {}}
    assert bvs.status("River", "RIVERSIDE HOSPITAL INC D B A RIVER", "exact", review) == "unreviewed"
    assert bvs.status("UK-Med", "CAP DIGISOFT SOLUTIONS INC DBA MED", "exact", review) == "unreviewed"
    assert bvs.status("Adyen", "Adyen N.V.", "exact", review) == "kept"                     # read and accepted
    assert bvs.status("Arcadia", "Arcadia Ltd", "exact", review) == "kept"                  # six letters and more: as before
    assert bvs.status("EY GDS", "EY GDS Limited", "exact", review) == "unreviewed"            # letters are counted, not the space
    assert bvs.status("Moss", "AB MOSS LIMITED", "exact", {"accepted": {}, "rejected": {"Moss": ["AB MOSS LIMITED"]}}) == "rejected"


def test_load_review_without_a_file_means_no_verdicts(tmp_path):
    assert bvs.load_review(tmp_path / "missing.json") == {"accepted": {}, "rejected": {}}


def _sources(d: Path) -> Path:
    d.mkdir()
    (d / "uk_register.csv").write_text("Organisation Name,Town/City,County,Type & Rating,Route\n"
                                       "Stripe Payments UK Ltd,London,,Worker (A rating),Skilled Worker\n"
                                       "Phoenix Software Limited,York,,Worker (A rating),Skilled Worker\n"
                                       "Mollie B.V. London Branch,London,,Worker (A rating),Skilled Worker\n", encoding="utf-8")
    (d / "nl_register.html").write_text('<tr><th scope="row">Mollie B.V.</th><td>34259528</td></tr>', encoding="utf-8")
    _xlsx(d / "ie_companies_2025.xlsx", [("Employer Name", "Permits Issued Grand Total"), ("Stripe Technology Europe Limited", 4)])
    (d / "gist.json").write_text(GIST, encoding="utf-8")
    (d / "shubheksha.md").write_text(SHUBHEKSHA, encoding="utf-8")
    meta = {"uk": {"title": "uk", "files": ["uk_register.csv"]}, "nl": {"title": "nl", "files": ["nl_register.html"]},
            "ie": {"title": "ie", "years": [2025], "files": ["ie_companies_2025.xlsx"]},
            "lists": {"title": "lists", "files": ["gist.json", "shubheksha.md"]}}
    (d / "sources.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


COMPANIES = [{"name": "Stripe", "ats": "greenhouse"}, {"name": "Mollie", "ats": "greenhouse"},
             {"name": "Phoenix", "ats": "ashby"}, {"name": "Acme", "ats": "lever"}]


def test_build_writes_kept_evidence_with_each_sources_own_name(tmp_path):
    review = {"accepted": {"Stripe": ["Stripe Payments UK Ltd", "Stripe Technology Europe Limited"]},
              "rejected": {"Phoenix": ["Phoenix Software Limited"]}}
    data, cands = bvs.build(_sources(tmp_path / "src"), COMPANIES, review)
    assert data["companies"] == {
        "Stripe": [{"source": "uk", "match": "loose", "names": {"Stripe Payments UK Ltd": ["Skilled Worker"]}},
                   {"source": "ie", "match": "loose", "names": {"Stripe Technology Europe Limited": {"2025": 4}}},
                   {"source": "lists", "match": "exact", "names": {"Stripe": ["shubheksha list: London, UK",
                                                                               "shubheksha list: Dublin, IE"]}}],
        "Mollie": [{"source": "uk", "match": "exact", "names": {"Mollie B.V. London Branch": ["Skilled Worker"]}},
                  {"source": "nl", "match": "exact", "names": {"Mollie B.V.": "34259528"}}]}
    assert {k: v["entries"] for k, v in data["sources"].items()} == {"uk": 3, "nl": 1, "ie": 1, "lists": 5}
    assert all("files" not in v for v in data["sources"].values())
    assert ("Phoenix", "uk", "loose", "Phoenix Software Limited", ["Skilled Worker"]) in cands   # still in the report


def test_an_unreviewed_loose_match_is_not_evidence(tmp_path):
    data, _ = bvs.build(_sources(tmp_path / "src"), COMPANIES, {"accepted": {}, "rejected": {}})
    assert [e["source"] for e in data["companies"]["Stripe"]] == ["lists"]
    assert "Phoenix" not in data["companies"] and "Acme" not in data["companies"]


def test_seeds_are_the_list_names_not_on_companies_json(tmp_path):
    assert bvs.seeds(_sources(tmp_path / "src"), COMPANIES) == ["Google", "Monzo", "QuantumBlack", "Zalando"]


def test_main_offline_writes_the_file_report_and_seeds(tmp_path, capsys):
    src = _sources(tmp_path / "src")
    (tmp_path / "companies.json").write_text(json.dumps(COMPANIES), encoding="utf-8")
    out, report, seeds = tmp_path / "v.json", tmp_path / "r.csv", tmp_path / "s.txt"
    assert bvs.main(["--offline", "--sources", str(src), "--companies", str(tmp_path / "companies.json"), "--out", str(out),
                     "--review", str(tmp_path / "none.json"), "--report", str(report), "--emit-seeds", str(seeds)]) == 0
    printed = capsys.readouterr().out
    assert "2 of 4 companies have evidence" in printed and "unreviewed (loose, or exact on a short name) (not used" in printed
    assert set(json.loads(out.read_text(encoding="utf-8"))["companies"]) == {"Stripe", "Mollie"}
    assert report.read_text(encoding="utf-8").splitlines()[0] == "Status,Company,ATS,Source,Match,Source's name,Detail"
    assert "unreviewed,Phoenix,ashby,uk,loose,Phoenix Software Limited" in report.read_text(encoding="utf-8")
    assert seeds.read_text(encoding="utf-8").split() == ["Google", "Monzo", "QuantumBlack", "Zalando"]


def test_main_offline_without_downloads_stops(tmp_path):
    with pytest.raises(SystemExit, match="nothing downloaded"):
        bvs.main(["--offline", "--sources", str(tmp_path / "empty")])


class _Resp:
    def __init__(self, text="", content=b"", data=None):
        self.text, self.content, self._data = text, content, data

    def json(self):
        return self._data


def test_download_finds_each_file_from_its_page(tmp_path, monkeypatch):
    """The CSV from GOV.UK's content API, the IND page's date, DETE's two latest years: no network (requests stubbed)."""
    calls = []

    def fake_get(url, timeout=120):
        calls.append(url)
        if url == bvs.UK_CONTENT_API:
            return _Resp(data={"title": "Register of licensed sponsors: workers", "public_updated_at": "2026-10-20T09:40:36+01:00",
                               "details": {"attachments": [{"url": "https://x/a.pdf", "content_type": "application/pdf"},
                                                           {"url": "https://x/register.csv", "content_type": "text/csv"}]}})
        if url == bvs.NL_PAGE:
            return _Resp(text="<p>This register was last updated on 5 October 2026.</p>")
        if url == bvs.IE_STATS:
            return _Resp(text=" ".join(f'<a href="/en/publications/employment-permit-statistics-{y}.html">' for y in (2024, 2025, 2026)))
        if url.endswith("statistics-2025.html") or url.endswith("statistics-2026.html"):
            return _Resp(text='<a href="/en/publications/publication-files/by-county.xlsx"></a>'
                              '<a href="/en/publications/publication-files/permits-issued-to-companies.xlsx"></a>')
        if "H1B_Hub" in url:                                   # the copy has no year newer than 2024
            if "_2024.csv" not in url:
                raise RuntimeError("404 Not Found")
            return _Resp(content=H1B.encode("utf-16"))
        if url == bvs.CA_API:
            return _Resp(data={"result": {"resources": CKAN}})
        return _Resp(text="{}", content=b"bytes")

    monkeypatch.setattr(bvs, "_get", fake_get)
    meta = bvs.download(tmp_path)
    assert "https://x/register.csv" in calls and "https://x/a.pdf" not in calls
    assert meta["uk"]["published"] == "2026-10-20" and meta["uk"]["licence"] == "Open Government Licence v3.0"
    assert meta["nl"]["published"] == "2026-10-05"
    assert meta["ie"]["years"] == [2025, 2026] and not any("statistics-2024" in c for c in calls)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "ca_lmia_2025Q3.xlsx", "ca_lmia_2025Q4.xlsx", "ca_lmia_2026Q1.xlsx", "ca_lmia_2026Q2.xlsx", "gist.json",
        "ie_companies_2025.xlsx", "ie_companies_2026.xlsx", "nl_register.html", "relocate.md", "shubheksha.md", "sources.json",
        "uk_register.csv", "us_h1b.csv"]
    assert bvs.RELOCATE_RAW in calls and "CC0-1.0" in meta["lists"]["licence"]
    assert meta["us"]["years"] == ["2024"] and meta["us"]["file"].endswith("Employer_Information_2024.csv")
    assert meta["ca"]["quarters"] == ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]           # the last four, French files left out
    assert not any("fr.xlsx" in c or "2025q2" in c for c in calls)


def test_the_shipped_dataset_and_review_file_are_well_formed():
    data = json.loads((ROOT / "job_hunt" / "data" / "visa_sponsors.json").read_text(encoding="utf-8"))
    assert set(data["sources"]) == {"uk", "nl", "ie", "us", "ca", "lists"}
    assert data["companies"] and all(e["source"] in data["sources"] and e["match"] in ("exact", "squashed", "loose") and e["names"]
                                     for ev in data["companies"].values() for e in ev)
    review = json.loads((ROOT / "scripts" / "visa_sponsor_review.json").read_text(encoding="utf-8"))
    for verdict in ("accepted", "rejected"):
        assert all(isinstance(v, list) and all(isinstance(n, str) for n in v) for v in review[verdict].values())
    for company, ev in data["companies"].items():           # nothing rejected by hand made it into the file
        assert not {n for e in ev for n in e["names"]} & set(review["rejected"].get(company, []))
        if len(bvs.exact_key(company).replace(" ", "")) <= bvs.SHORT_KEY:      # a short name's exact match was read (T144 review)
            assert all(n in review["accepted"].get(company, []) for e in ev if e["match"] == "exact" for n in e["names"]), company


RELOCATE = """# Intro

# 🏢 Companies hiring internationally

| Company name | Location(s) | Careers page |
|-------|--------------|---------------|
| Applike Group | Hamburg 🇩🇪 | https://applike-group.com/jobs |
| Byborg Enterprises | Luxembourg 🇱🇺 <br> Budapest 🇭🇺 | https://careers.smartrecruiters.com/DoclerHolding |
| CloudLinux | Remote 🌍 | https://www.cloudlinux.com/jobs |
| BandLab | Singapore 🇸🇬 | https://www.bandlab.com/careers |

# 🗣️ Job interviews
| Not | a | company |
"""


def test_parse_relocate_reads_the_company_table_with_its_flags_as_countries():
    assert bvs.parse_relocate(RELOCATE) == {"Applike Group": ["Hamburg, Germany"], "Byborg Enterprises": ["Luxembourg, Luxembourg", "Budapest, Hungary"],
                                            "CloudLinux": ["Remote"], "BandLab": ["Singapore, Singapore"]}


def test_an_older_download_without_the_relocate_file_still_builds(tmp_path):
    data, _ = bvs.build(_sources(tmp_path / "src"), COMPANIES, {"accepted": {}, "rejected": {}})
    assert data["companies"]["Stripe"][0]["source"] == "lists"


def test_a_download_with_the_relocate_file_records_its_companies_with_their_places(tmp_path):
    """Review: a build that skipped relocate.md passed every test (only the parser and the build without it were tested)."""
    src = _sources(tmp_path / "src")
    (src / "relocate.md").write_text(RELOCATE, encoding="utf-8")
    data, _ = bvs.build(src, COMPANIES + [{"name": "Applike Group", "ats": "personio"}], {"accepted": {}, "rejected": {}})
    assert data["companies"]["Applike Group"] == [{"source": "lists", "match": "exact",
                                                   "names": {"Applike Group": ["relocate.me list: Hamburg, Germany"]}}]



# ── T143: the USA's H-1B approvals and Canada's positive LMIA employers ───────

H1B = ("Line by line\tFiscal Year   \tEmployer (Petitioner) Name\tTax ID\tIndustry (NAICS) Code\tPetitioner City\t"
       "Petitioner State\tPetitioner Zip Code\tInitial Approval\tInitial Denial\tContinuing Approval\tContinuing Denial\n"
       "1\t2024\t\t3581\t54\tLAFAYETTE\tCA\t94549\t0\t0\t1\t0\n"                       # no name: left out
       "2\t2024\tSTRIPE INC\t1\t54\tSOUTH SAN FRANCISCO\tCA\t94080\t30\t1\t1,205\t0\n"
       "3\t2024\tSTRIPE INC\t2\t54\tSEATTLE\tWA\t98101\t2\t0\t3\t0\n"                   # another tax id: added up
       "4\t2024\tDENIED ONLY LLC\t3\t54\tAUSTIN\tTX\t78701\t0\t4\t0\t2\n")              # no approval: no record

CKAN = [{"name": f"{q}-Employers Who Were Issued a Positive LMIA", "format": "XLSX", "language": [lang],
         "url": f"https://x/{q.lower()}_{lang}.xlsx"}
        for q in ("2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2") for lang in ("en", "fr")] + [
        {"name": "2016-Employers ...", "format": "CSV", "language": ["en"], "url": "https://x/2016.csv"}]


def test_parse_us_adds_up_an_employers_rows_in_either_encoding(tmp_path):
    want = {"STRIPE INC": {"2024": [32, 1208]}}
    (tmp_path / "a.csv").write_bytes(H1B.encode("utf-16"))           # what the hub writes
    (tmp_path / "b.csv").write_text(H1B, encoding="utf-8")
    assert bvs.parse_us(tmp_path / "a.csv") == want and bvs.parse_us(tmp_path / "b.csv") == want


def _lmia(path, rows):
    _xlsx(path, [("Employers Who Were Issued a Positive LMIA, January to March 2026",),
                 ("Province/Territory", "Program Stream", "Employer", "Address", "Occupation", "Incorporate Status",
                  "Approved LMIAs", "Approved Positions"), *rows,
                 ("1. The source for all information in this report is ESDC's LMIA System.",)])


def test_parse_ca_counts_positions_and_the_software_ones(tmp_path):
    _lmia(tmp_path / "q.xlsx", [
        ("Ontario      ", "Global Talent Stream  ", "Shopify Inc.", "Ottawa, ON", "21231-Software engineers and designers", "Yes", 1, 3),
        ("Ontario", "High Wage          ", "Shopify Inc.", "Toronto, ON", "10010-Financial managers", "Yes", 1, 1),
        ("Ontario", "High Wage", "Shopify Inc.", "Toronto, ON", "21211-Data scientists", "Yes", 1, 2),
        ("Ontario", "High Wage", "Shopify Inc.", "Toronto, ON", "20012-Computer and information systems managers", "Yes", 1, 1),
        ("Quebec", "Low Wage", "Restaurant ABC", "Laval, QC", "65201-Food counter attendants", "Unknown", 1, 4)])
    assert bvs.parse_ca(tmp_path / "q.xlsx") == {
        "Shopify Inc.": {"positions": 7, "tech": 6, "streams": ["Global Talent Stream", "High Wage"]},
        "Restaurant ABC": {"positions": 4, "tech": 0, "streams": ["Low Wage"]}}


def _sources_t143(d: Path) -> Path:
    _sources(d)
    (d / "us_h1b.csv").write_bytes(H1B.encode("utf-16"))
    _lmia(d / "ca_lmia_2026Q1.xlsx", [("Ontario", "Global Talent Stream", "Stripe Canada Inc", "Toronto, ON",
                                       "21232-Software developers and programmers", "Yes", 1, 2)])
    meta = json.loads((d / "sources.json").read_text(encoding="utf-8"))
    meta["us"] = {"title": "us", "years": ["2024"], "files": ["us_h1b.csv"]}
    meta["ca"] = {"title": "ca", "quarters": ["2026Q1"], "files": ["ca_lmia_2026Q1.xlsx"]}
    (d / "sources.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


def test_build_records_h1b_approvals_and_positive_lmias(tmp_path):
    data, _ = bvs.build(_sources_t143(tmp_path / "src"), COMPANIES, {"accepted": {}, "rejected": {}})
    stripe = {e["source"]: e for e in data["companies"]["Stripe"]}
    assert stripe["us"] == {"source": "us", "match": "exact", "names": {"STRIPE INC": {"2024": [32, 1208]}}}
    assert stripe["ca"] == {"source": "ca", "match": "exact",      # "Canada" is a country word, like "UK"
                            "names": {"Stripe Canada Inc": {"2026Q1": {"positions": 2, "tech": 2, "streams": ["Global Talent Stream"]}}}}
    assert data["sources"]["us"]["entries"] == 1 and data["sources"]["ca"]["entries"] == 1


def test_offline_with_a_newer_hub_export_replaces_only_the_us_file(tmp_path, capsys):
    src = _sources_t143(tmp_path / "src")
    newer = tmp_path / "Employer Information.csv"
    newer.write_bytes(H1B.replace("\t2024\t", "\t2025\t").encode("utf-16"))
    (tmp_path / "companies.json").write_text(json.dumps(COMPANIES), encoding="utf-8")
    out = tmp_path / "out.json"
    assert bvs.main(["--offline", "--us-h1b", str(newer), "--sources", str(src), "--companies", str(tmp_path / "companies.json"),
                     "--out", str(out), "--review", str(tmp_path / "none.json")]) == 0
    meta = json.loads((src / "sources.json").read_text(encoding="utf-8"))
    assert meta["us"]["years"] == ["2025"] and meta["us"]["file"] == "Employer Information.csv" and meta["ca"]["quarters"] == ["2026Q1"]
    stripe = {e["source"]: e["names"] for e in json.loads(out.read_text(encoding="utf-8"))["companies"]["Stripe"]}
    assert stripe["us"] == {"STRIPE INC": {"2025": [32, 1208]}}


def test_every_flag_gets_its_countrys_name():
    assert bvs._flags_to_names("Toronto 🇨🇦") == "Toronto, Canada" and bvs._flags_to_names("Lisbon 🇵🇹") == "Lisbon, Portugal"


# ── T144: a name built from a web address ──────────────────────────────────────

@pytest.mark.parametrize("name, key", [
    ("Cloudimperiumgames", "cloudimperiumgames"), ("Cloud Imperium Games Ltd", "cloudimperiumgames"), ("Basic-Fit B.V.", "basicfit"),
    ("Ace Ltd", ""), ("ING", ""),                                       # under six letters: too many other firms
])
def test_squashed_key(name, key):
    assert bvs.squashed_key(name) == key


def test_a_name_from_a_web_address_matches_the_registers_spaced_name_as_squashed():
    idx = bvs.Index({"Cloud Imperium Games Ltd": [], "Basic-Fit B.V.": [], "Ace Ltd": []})
    assert idx.match("Cloudimperiumgames") == ("squashed", ["Cloud Imperium Games Ltd"])
    assert idx.match("Basicfit") == ("squashed", ["Basic-Fit B.V."])
    assert idx.match("Cloud Imperium Games") == ("exact", ["Cloud Imperium Games Ltd"])          # the exact match still comes first
    assert idx.match("Acedia") == (None, [])


def test_a_squashed_match_is_kept_without_a_review_and_a_rejection_still_wins():
    review = {"accepted": {}, "rejected": {"Basicfit": ["Basic-Fit B.V."]}}
    assert bvs.status("Cloudimperiumgames", "Cloud Imperium Games Ltd", "squashed", review) == "kept"
    assert bvs.status("Basicfit", "Basic-Fit B.V.", "squashed", review) == "rejected"


# ── T144 (and T145): a name accepted by hand is an alias ─────────────────────────────────────────────────────────

def test_a_name_accepted_by_hand_matches_although_no_rule_proposes_it():
    idx = bvs.Index({"SFDC Ireland Limited": {"2025": 12}, "WAL MART ASSOCIATES INC": {}, "Salesforce UK Limited": []})
    assert idx.match("Salesforce") == ("exact", ["Salesforce UK Limited"])                                         # a rule's match
    assert idx.match("Salesforce", ["SFDC Ireland Limited"]) == ("exact", ["SFDC Ireland Limited", "Salesforce UK Limited"])
    assert idx.match("Walmart") == (None, [])
    assert idx.match("Walmart", ["WAL MART ASSOCIATES INC"]) == ("loose", ["WAL MART ASSOCIATES INC"])
    assert idx.match("Walmart", ["NOT IN THIS SOURCE"]) == (None, [])                      # an alias another source holds


def test_the_build_keeps_an_alias_the_review_accepted_and_only_that():
    review = {"accepted": {"Salesforce": ["SFDC Ireland Limited"]}, "rejected": {}}
    ie = bvs.Index({"SFDC Ireland Limited": {"2025": 12}, "SFDC Ireland Ltd Other": {"2025": 1}})
    cands = bvs.candidates([{"name": "Salesforce", "ats": "greenhouse"}], {"ie": ie}, review)
    assert [(c[0], c[1], c[2], c[3]) for c in cands] == [("Salesforce", "ie", "loose", "SFDC Ireland Limited")]
    assert bvs.match_companies(cands, review) == {"Salesforce": [{"source": "ie", "match": "loose", "names": {"SFDC Ireland Limited": {"2025": 12}}}]}
    assert bvs.match_companies(bvs.candidates([{"name": "Salesforce", "ats": "greenhouse"}], {"ie": ie}), review) == {}     # no alias, no match


NO_REVIEW = {"accepted": {}, "rejected": {}}


def test_build_uses_the_aliases_of_the_review(tmp_path):
    src = _sources(tmp_path / "src")
    review = {"accepted": {"Acme": ["Stripe Technology Europe Limited"]}, "rejected": {}}
    data, _ = bvs.build(src, [{"name": "Acme", "ats": "lever"}], review)
    assert data["companies"] == {"Acme": [{"source": "ie", "match": "loose", "names": {"Stripe Technology Europe Limited": {"2025": 4}}}]}
    assert bvs.build(src, [{"name": "Acme", "ats": "lever"}], NO_REVIEW)[0]["companies"] == {}

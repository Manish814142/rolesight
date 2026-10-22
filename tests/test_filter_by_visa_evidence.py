"""T144: scripts/filter_by_visa_evidence.py keeps a company only when it shows evidence of sponsoring visas (no network)."""
import csv
import importlib.util
import json
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("fbve", ROOT / "scripts" / "filter_by_visa_evidence.py")
fbve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fbve)
bvs = fbve.bvs

NO_REVIEW = {"accepted": {}, "rejected": {}}


def _idx(**sources):
    return {k: bvs.Index(v) for k, v in sources.items()}


def _e(name, ats="greenhouse", places=("United Kingdom",)):
    return {"name": name, "ats": ats, "slug": name.lower(), **({"places": list(places)} if places else {})}


def test_a_register_for_a_country_it_hires_in_is_evidence():
    idx = _idx(uk={"Monzo Bank Ltd": ["Skilled Worker"]}, nl={"Adyen N.V.": "34259528"})
    assert fbve.judge(_e("Monzo Bank"), idx, NO_REVIEW, {})[:2] == ("keep", ["uk: Monzo Bank Ltd"])
    # on the Dutch register but hiring only in the UK: not evidence for the UK
    assert fbve.judge(_e("Adyen"), idx, NO_REVIEW, {})[0] == "drop"
    assert fbve.judge(_e("Adyen", places=("Netherlands",)), idx, NO_REVIEW, {})[0] == "keep"


def test_a_name_from_a_web_address_matches_as_squashed():
    idx = _idx(uk={"Cloud Imperium Games Ltd": ["Skilled Worker"]})
    assert fbve.judge(_e("Cloudimperiumgames", "personio"), idx, NO_REVIEW, {})[:2] == ("keep", ["uk: Cloud Imperium Games Ltd"])


def test_a_weak_match_is_for_review_until_somebody_accepts_it_and_a_rejection_drops_it():
    idx = _idx(uk={"Allfunds Bank International SA": ["Skilled Worker"]})
    decision, evidence, weak = fbve.judge(_e("Allfunds"), idx, NO_REVIEW, {})
    assert (decision, evidence, weak) == ("review", [], ["uk: Allfunds Bank International SA"])
    accepted = {"accepted": {"Allfunds": ["Allfunds Bank International SA"]}, "rejected": {}}
    assert fbve.judge(_e("Allfunds"), idx, accepted, {})[0] == "keep"
    rejected = {"accepted": {}, "rejected": {"Allfunds": ["Allfunds Bank International SA"]}}
    assert fbve.judge(_e("Allfunds"), idx, rejected, {})[0] == "drop"


def test_a_posting_that_offers_visa_sponsorship_is_evidence_and_relocation_alone_is_not():
    assert fbve.judge(_e("Wheely"), {}, NO_REVIEW, {"Wheely": {"visa": {"offered": 2}}})[:2] == ("keep", ["posting offers visa sponsorship"])
    assert fbve.judge(_e("Wheely"), {}, NO_REVIEW, {"Wheely": {"visa": {"silent": 5}, "reloc": 3}})[0] == "drop"


def test_a_community_list_counts_for_the_places_its_entry_names():
    idx = _idx(lists={"Mollie": ["relocate.me list: Amsterdam, Netherlands"]})
    assert fbve.judge(_e("Mollie", places=("Netherlands",)), idx, NO_REVIEW, {})[0] == "keep"
    assert fbve.judge(_e("Mollie", places=("Germany",)), idx, NO_REVIEW, {})[0] == "drop"
    idx = _idx(lists={"Mollie": ["relocate.me list: Remote"]})
    assert fbve.judge(_e("Mollie", places=("Germany",)), idx, NO_REVIEW, {})[0] == "keep"


def test_a_workday_entry_records_every_country_so_any_record_counts():
    idx = _idx(us={"BARCLAYS INC": {"2024": [10, 5]}})
    assert fbve.judge(_e("Barclays", "workday", places=("United Kingdom", "Germany")), idx, NO_REVIEW, {})[0] == "keep"
    assert fbve.judge(_e("Barclays", "greenhouse", places=("United Kingdom",)), idx, NO_REVIEW, {})[0] == "drop"


def _xlsx(path, rows):
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(path)


def test_main_writes_the_kept_entries_and_a_report(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "uk_register.csv").write_text("Organisation Name,Town/City,County,Type & Rating,Route\n"
                                         "Monzo Bank Ltd,London,,Worker (A rating),Skilled Worker\n"
                                         "Allfunds Bank International SA,London,,Worker (A rating),Skilled Worker\n", encoding="utf-8")
    (src / "nl_register.html").write_text('<tr><th scope="row">Adyen N.V.</th><td>34259528</td></tr>', encoding="utf-8")
    _xlsx(src / "ie.xlsx", [("Employer Name", "Permits Issued Grand Total"), ("Stripe Technology Europe Limited", 4)])
    (src / "gist.json").write_text(json.dumps({"files": {"x.md": {"content": "**London**\n* [Google](x)\n"}}}), encoding="utf-8")
    (src / "shubheksha.md").write_text("| Name | Location(s) |\n|---|---|\n", encoding="utf-8")
    (src / "sources.json").write_text(json.dumps({
        "uk": {"files": ["uk_register.csv"]}, "nl": {"files": ["nl_register.html"]},
        "ie": {"years": [2025], "files": ["ie.xlsx"]}, "lists": {"files": ["gist.json", "shubheksha.md"]}}), encoding="utf-8")
    cand = tmp_path / "v.json"
    cand.write_text(json.dumps([_e("Monzo Bank"), _e("Nobody Ltd"), _e("Allfunds"), _e("Wheely")]), encoding="utf-8")
    post = tmp_path / "p.json"
    post.write_text(json.dumps({"Wheely": {"visa": {"offered": 1}}}), encoding="utf-8")
    out, rep = tmp_path / "kept.json", tmp_path / "r.csv"
    assert fbve.main(["--candidates", str(cand), "--out", str(out), "--report", str(rep), "--postings", str(post),
                      "--sources", str(src), "--review", str(tmp_path / "none.json")]) == 0
    assert [e["name"] for e in json.loads(out.read_text(encoding="utf-8"))] == ["Monzo Bank", "Wheely"]
    rows = list(csv.DictReader(open(rep, encoding="utf-8")))
    assert [(r["Decision"], r["Company"]) for r in rows] == [("drop", "Nobody Ltd"), ("keep", "Monzo Bank"), ("keep", "Wheely"),
                                                             ("review", "Allfunds")]
    assert next(r for r in rows if r["Company"] == "Allfunds")["Weak matches (unreviewed)"].startswith("uk: Allfunds Bank")


def test_main_without_downloads_stops(tmp_path):
    with pytest.raises(SystemExit, match="nothing downloaded"):
        fbve.main(["--candidates", str(tmp_path / "x.json"), "--out", str(tmp_path / "o.json"), "--sources", str(tmp_path / "empty")])

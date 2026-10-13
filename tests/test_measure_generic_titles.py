"""T69(g): the classifier behind scripts/measure_generic_titles.py (no network; a hand-made fetch)."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("mgt", Path(__file__).resolve().parent.parent / "scripts" / "measure_generic_titles.py")
mgt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mgt)


def _r(title, location="Bengaluru, India", company="Acme", posted="", remote=False):
    return {"title": title, "location": location, "company": company, "ats": "greenhouse", "posted_at": posted, "is_remote": remote}


def test_bare_titles_are_seniority_engineer_and_a_level_only():
    for t in ("Engineer", "Senior Engineer", "Sr. Engineer", "Engineer II", "Engineer III", "Senior Engineer 2", "Engineer, I"):
        assert mgt.kind(_r(t)) == "bare", t


def test_other_engineer_titles_are_qualified_and_non_engineers_are_other():
    assert mgt.kind(_r("Cloud Engineer")) == "qualified"
    assert mgt.kind(_r("Senior Engineer, Payments")) == "qualified"
    assert mgt.kind(_r("Business Analyst")) == "other"


def test_a_title_the_filter_already_decides_is_not_counted():
    assert mgt.kind(_r("Backend Engineer")) is None          # include word: it passes
    assert mgt.kind(_r("Lead Engineer")) is None             # exclude word: rejected on purpose
    assert mgt.kind(_r("Embedded Engineer")) is None


def test_a_job_outside_india_is_not_counted():
    assert mgt.kind(_r("Senior Engineer", location="Austin, TX")) is None
    assert mgt.kind(_r("Senior Engineer", location="Remote", remote=True)) == "bare"


def test_analyse_counts_survivors_per_company_and_the_recent_ones():
    rows = [_r("Backend Engineer", company="Acme"), _r("Senior Engineer", company="Acme", posted="2000-01-01"),
            _r("Senior Engineer", company="Beta"), _r("Cloud Engineer", company="Beta")]
    res = mgt.analyse(rows, days=7)
    assert res["survivors"] == 1 and res["survivors_by_company"]["Acme"] == 1
    assert len(res["dropped"]["bare"]) == 2 and len(res["dropped"]["qualified"]) == 1
    assert len(res["recent"]["bare"]) == 1, "the 2000-01-01 posting is outside the window; the undated one is kept"

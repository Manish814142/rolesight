"""T69(g), T96: the classifier behind scripts/measure_generic_titles.py (no network; a hand-made fetch)."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("mgt", Path(__file__).resolve().parent.parent / "scripts" / "measure_generic_titles.py")
mgt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mgt)


def _r(title, location="Bengaluru, India", company="Acme", posted="", remote=False):
    return {"title": title, "location": location, "company": company, "ats": "greenhouse", "posted_at": posted, "is_remote": remote}


def test_generic_titles_are_no_longer_dropped():
    """T96: they reach Gemini, so the script has nothing to count for them."""
    for t in ("Engineer", "Senior Engineer", "Sr. Engineer", "Engineer II", "Engineer III, Software", "Sr Software Application Engineer"):
        assert mgt.kind(_r(t)) is None, t


def test_other_engineer_titles_are_qualified_and_non_engineers_are_other():
    assert mgt.kind(_r("Cloud Engineer")) == "qualified"
    assert mgt.kind(_r("Data Engineer")) == "qualified"
    assert mgt.kind(_r("Business Analyst")) == "other"


def test_a_title_the_filter_already_decides_is_not_counted():
    assert mgt.kind(_r("Backend Engineer")) is None          # include word: it passes
    assert mgt.kind(_r("Lead Engineer")) is None             # exclude word: rejected on purpose
    assert mgt.kind(_r("Embedded Engineer")) is None


def test_a_job_outside_india_is_not_counted():
    assert mgt.kind(_r("Data Engineer", location="Austin, TX")) is None
    assert mgt.kind(_r("Data Engineer", location="Remote", remote=True)) == "qualified"


def test_analyse_counts_survivors_per_company_and_the_recent_ones():
    rows = [_r("Backend Engineer", company="Acme"), _r("Senior Engineer", company="Acme"),
            _r("Data Engineer", company="Beta", posted="2000-01-01"), _r("Data Engineer", company="Beta"),
            _r("Cloud Engineer", company="Beta")]
    res = mgt.analyse(rows, days=7)
    assert res["survivors"] == 2 and res["survivors_by_company"]["Acme"] == 2
    assert len(res["dropped"]["qualified"]) == 3
    assert len(res["recent"]["qualified"]) == 2, "the 2000-01-01 posting is outside the window; the undated ones are kept"

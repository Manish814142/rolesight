"""T138 (T108 part 3): the rubric's location rule follows your places; the Visa column (job_hunt/visa.py)."""
import csv
import logging

import pytest

from job_hunt import llm_utils, visa
from job_hunt import places as pl
from job_hunt.exporter import export_jobs_to_csv, job_from_db_row


@pytest.fixture(autouse=True)
def _reset():
    yield
    pl.configure_places(pl.INDIA)
    llm_utils.configure_rubric({})


def _cfg(*countries, home=None):
    cand = {"countries": list(countries)}
    if home:
        cand["home_country"] = home
    return {"candidate": cand}


# ── the rubric ───────────────────────────────────────────────────────────────

def test_india_keeps_the_rubric_text_and_id():
    llm_utils.configure_rubric({})
    assert llm_utils.SCORING_RUBRIC == llm_utils.DEFAULT_SCORING_RUBRIC and llm_utils.rubric_id() == "82e017b4"
    llm_utils.configure_rubric(_cfg("India"))
    assert llm_utils.rubric_id() == "82e017b4"


def test_other_countries_rewrite_only_the_two_location_lines():
    llm_utils.configure_rubric(_cfg("UK", "Germany"))
    text = llm_utils.SCORING_RUBRIC
    assert llm_utils.INDIA_LOCATION_RULE not in text and "on-site presence outside India" not in text
    assert "on-site or hybrid presence outside United Kingdom or Germany, cap score at <= 30" in text
    assert "The candidate lives in India and needs the employer to sponsor a work visa for any role outside India" in text
    assert "A posting that says nothing about visas is not capped for that." in text
    assert "   - Location fits (United Kingdom or Germany or Remote)." in text
    back = (text.replace(llm_utils.location_rule(pl.places_from_config(_cfg("UK", "Germany"))), llm_utils.INDIA_LOCATION_RULE)
                .replace("   - Location fits (United Kingdom or Germany or Remote).", llm_utils.INDIA_LOCATION_FIT))
    assert back == llm_utils.DEFAULT_SCORING_RUBRIC                       # nothing else changed
    assert llm_utils.rubric_id() != "82e017b4"


def test_a_rubric_file_with_the_built_in_rule_1_is_rewritten_too(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rubric.md").write_text(llm_utils.DEFAULT_SCORING_RUBRIC.replace("~3.3 years", "~8 years"))
    llm_utils.configure_rubric({"candidate": {"rubric_file": "rubric.md", "countries": ["Singapore"]}})
    assert "outside Singapore, cap score" in llm_utils.SCORING_RUBRIC and "~8 years" in llm_utils.SCORING_RUBRIC


def test_a_rule_1_the_person_rewrote_is_kept_with_a_warning(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    mine = llm_utils.DEFAULT_SCORING_RUBRIC.replace(llm_utils.INDIA_LOCATION_RULE, "   Cap at 30 anything outside Berlin.")
    (tmp_path / "rubric.md").write_text(mine)
    with caplog.at_level(logging.WARNING):
        llm_utils.configure_rubric({"candidate": {"rubric_file": "rubric.md", "countries": ["Germany"]}})
    assert "Cap at 30 anything outside Berlin." in llm_utils.SCORING_RUBRIC
    assert "rule 1 is not the built-in India text" in caplog.text and "Germany" in caplog.text


def test_structured_instructions_follow_the_places_and_come_back():
    default = llm_utils.STRUCTURED_INSTRUCTIONS
    llm_utils.configure_rubric(_cfg("UAE"))
    assert "100 for United Arab Emirates or remote open to candidates there" in llm_utils.STRUCTURED_INSTRUCTIONS
    assert "on-site presence outside India" not in llm_utils.STRUCTURED_INSTRUCTIONS
    llm_utils.configure_rubric({})
    assert llm_utils.STRUCTURED_INSTRUCTIONS == default


def test_the_structured_cap_label_names_the_visa_for_other_places():
    facts = {"stack_fit": 90, "role_fit": 90, "seniority_fit": 90, "location_fit": 10, "min_years": 3,
             "accepts_candidate_stack": True, "onsite_outside_india": True, "aimed_at_freshers": False, "reason": "r"}
    assert "outside India" in str(llm_utils.combine_subscores(facts))
    pl.configure_places(pl.places_from_config(_cfg("UK")))
    assert "no visa sponsorship" in str(llm_utils.combine_subscores(facts))


# ── the wording: citizenship and residence requirements (found in the end-to-end run, T140) ──────────────

@pytest.mark.parametrize("text, kind", [
    ("Due to the nature of the projects and specific client security clearance, this role requires the successful candidate "
     "to be a Singapore Citizen or PR of Singapore.", "refused"),
    ("Only Singapore Citizens and Singapore Permanent Residents (PRs) will be considered.", "refused"),
    ("Applicants must be Singapore Citizens.", "refused"),
    ("You must hold UK citizenship for this cleared role.", "refused"),
    ("Must be a European citizen or have a valid and independent working visa for Germany", "refused"),
    ("We welcome applicants regardless of citizenship or immigration status.", "silent"),
    ("Applicants will be considered without regard to race, citizenship status or national origin.", "silent"),
    ("or require any reasonable adjustments during the recruitment pr ocess, let us know", "silent"),   # "pr" is not PR
])
def test_citizenship_and_residence_requirements_are_refusals(text, kind):
    assert visa.wording(text)[0] == kind


# ── the visa note ────────────────────────────────────────────────────────────

RECORDS = {
    "Stripe": [{"source": "uk", "match": "loose", "names": {"Stripe Payments UK Ltd": ["Skilled Worker"]}},
               {"source": "ie", "match": "loose", "names": {"Stripe Technology Europe Limited": {"2025": 4, "2026": 2}}},
               {"source": "lists", "match": "exact", "names": {"Stripe": ["shubheksha list: London, UK"]}}],
    "Adyen": [{"source": "nl", "match": "exact", "names": {"Adyen N.V.": "34259528"}}],
}


@pytest.fixture
def records(monkeypatch):
    monkeypatch.setattr(visa, "_records", lambda: RECORDS)


@pytest.mark.parametrize("company, location, text, expected", [
    ("Stripe", "London, UK", "We are unable to sponsor visas for this role.",
     "Posting: no visa sponsorship; UK licensed sponsor; on a relocation list"),
    ("Stripe", "London, UK", "Visa sponsorship is available.", "Posting: offers visa sponsorship; UK licensed sponsor; on a relocation list"),
    ("Stripe", "Dublin, Ireland", "A great team.", "Not stated; 6 Irish work permits 2025-2026; on a relocation list"),
    ("Adyen", "Amsterdam, Netherlands", "We will verify your right to work.", "Posting: unclear; Dutch recognised sponsor"),
    ("Acme", "London, UK", "", "Not stated"),
    ("Stripe", "Remote - EMEA", "", "Not stated; UK licensed sponsor; on a relocation list"),   # a region of the UK
    ("Stripe", "Bengaluru, India", "No visa sponsorship.", ""),        # home country: no visa needed
    ("Stripe", "Remote", "", ""),                                      # remote with no place: no move
    ("Stripe", "London, UK; Pune, India", "", ""),                     # also at home
])
def test_note(records, company, location, text, expected):
    assert visa.note(company, location, text, pl.places_from_config(_cfg("UK", "India", "Netherlands", "Ireland"))) == expected


def test_india_alone_never_writes_a_note(records):
    assert visa.note("Stripe", "London, UK", "No visa sponsorship.", pl.INDIA) == ""


def test_the_shipped_records_are_read():
    assert "UK licensed sponsor" in visa.record("Canva", "United Kingdom")
    assert visa.record("No Such Company Ltd", "United Kingdom") == ""


# ── the CSV ──────────────────────────────────────────────────────────────────

def _row(**kw):
    return {"company": "Stripe", "title": "Backend Engineer", "location": "London, UK", "url": "https://x/1", "score": 80,
            "reason": "fits", **kw}


def test_the_visa_column_appears_only_when_a_job_has_a_note(tmp_path):
    with_note = export_jobs_to_csv([_row(visa="Not stated; UK licensed sponsor"), _row(visa="")], out_path=tmp_path / "a.csv")
    rows = list(csv.DictReader(open(with_note, encoding="utf-8")))
    assert rows[0]["Visa"] == "Not stated; UK licensed sponsor"
    without = export_jobs_to_csv([_row(visa=""), _row()], out_path=tmp_path / "b.csv")
    assert "Visa" not in open(without, encoding="utf-8").readline()


def test_export_from_the_database_writes_the_note_from_the_stored_description(records):
    db_row = {"company": "Stripe", "ats": "greenhouse", "title": "Backend Engineer", "location": "London, UK", "url": "u",
              "score": 80, "score_reason": "fits", "posted_at": "", "scored_at": "2026-10-21", "description": "No visa sponsorship."}
    assert job_from_db_row(db_row, 70)["visa"] == ""                       # India alone
    pl.configure_places(pl.places_from_config(_cfg("UK")))
    assert job_from_db_row(db_row, 70)["visa"] == "Posting: no visa sponsorship; UK licensed sponsor; on a relocation list"

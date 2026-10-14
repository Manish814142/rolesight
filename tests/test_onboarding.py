"""T103: `rolesight init [--resume FILE] [--yes]`, `rolesight check-filter`, the rubric file, and the scan reading them.

Gemini is stubbed: `personalize(..., generate=fake)`. The real drafting call was run by hand (see the T103 notes).
"""
import io
import json
import sys
from pathlib import Path

import pytest

from job_hunt import llm_utils, main, onboarding, prefilter
from job_hunt.llm_utils import DEFAULT_SCORING_RUBRIC, RubricError, rubric_id
from job_hunt.prefilter import TitleRules

ROOT = Path(__file__).resolve().parent.parent
FAKE_KEY = "AIza" + "-test-key-0123456789"     # built at run time: written out, gitleaks reads it as a key
RESUME = "# Asha Rao\nJava backend developer, 6 years. Spring Boot, Kafka, PostgreSQL, AWS. Pune.\n" + "Built payment services. " * 20


def _draft(**over):
    d = {"name": "Asha Rao", "profile": "6 YOE Java backend engineer. Stack: Java, Spring Boot, Kafka",
         "seeking": "Backend roles, hybrid in Pune", "not_suitable": "Frontend, QA, management",
         "include": ["java developer", "backend", "spring boot", "software engineer"],
         "exclude": ["principal", "director", "intern", "php", "frontend"],
         "generic_engineer_titles": True,
         "jobs": [{"company": "PayCo", "title": "Senior Developer", "start": "2020-08", "end": "present"},
                  {"company": "BankSoft", "title": "Developer", "start": "2019-01", "end": "2020-09"}],
         "rubric": DEFAULT_SCORING_RUBRIC.replace("~3.3 years", "~6 years")}
    d.update(over)
    return d


class FakeGemini:
    def __init__(self, draft=None, pdf_text="# Asha Rao\n" + "Java developer. " * 30):
        self.calls = []
        self.draft = draft or _draft()
        self.pdf_text = pdf_text

    def __call__(self, key, models, contents, schema=None):
        self.calls.append((key, models, contents, schema))
        if schema:                                                  # the settings: JSON
            return json.dumps({k: v for k, v in self.draft.items() if k != "rubric"})
        if isinstance(contents[0], bytes):                          # a PDF: its text
            return self.pdf_text
        return self.draft["rubric"]                                 # the rubric: plain text


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))          # not a terminal: nothing is asked
    return tmp_path


def _init_with(workdir, monkeypatch, fake, resume_name="asha.md", yes=False, key=FAKE_KEY):
    if key:
        monkeypatch.setenv("GEMINI_API_KEY", key)
    resume = workdir / resume_name
    if resume_name.endswith(".pdf"):
        resume.write_bytes(b"%PDF-1.4 fake")
    else:
        resume.write_text(RESUME)
    created = onboarding._scaffold(workdir)
    (workdir / ".env").unlink()                                  # the template's placeholder must not hide the test key
    onboarding.personalize(workdir, resume, created, yes, generate=fake)
    return json.loads((workdir / "config.json").read_text())


# -- plain init ----------------------------------------------------------------------------------------------------------

def test_plain_init_writes_the_rubric_file_the_example_config_names(workdir, capsys):
    main.init_project()
    config = json.loads((workdir / "config.json").read_text())
    assert config["candidate"]["rubric_file"] == "rubric.md"
    assert llm_utils.configure_rubric(config) == "rubric.md"
    assert rubric_id() == rubric_id(DEFAULT_SCORING_RUBRIC), "the written built-in rubric scores exactly like the built-in one"
    assert "init --resume" in capsys.readouterr().out


def test_the_example_config_carries_the_default_title_filter():
    for path in ("config.example.json", "job_hunt/data/config.example.json"):
        cand = json.loads((ROOT / path).read_text())["candidate"]
        assert TitleRules.from_config({"candidate": cand}) == TitleRules(), path


def test_without_titles_or_rubric_file_a_config_keeps_the_defaults():
    """Manish's config.json has neither: his filter and rubric are the defaults, unchanged by T103."""
    assert prefilter.configure_titles({"candidate": {"name": "x"}}) == TitleRules()
    assert llm_utils.configure_rubric({"candidate": {"name": "x"}}) == "built-in"
    assert llm_utils.SCORING_RUBRIC == DEFAULT_SCORING_RUBRIC


def test_a_missing_rubric_file_is_refused_with_what_to_do(workdir):
    with pytest.raises(RubricError, match="rolesight init"):
        llm_utils.configure_rubric({"candidate": {"rubric_file": "mine.md"}})


def test_a_rubric_file_changes_what_the_prompt_sends_and_its_id(workdir):
    (workdir / "mine.md").write_text("SCORING RUBRIC for Asha\n1. ...\n")
    llm_utils.configure_rubric({"candidate": {"rubric_file": "mine.md"}})
    assert llm_utils.SCORING_RUBRIC == "SCORING RUBRIC for Asha\n1. ..."
    assert rubric_id() != rubric_id(DEFAULT_SCORING_RUBRIC) and rubric_id() in llm_utils.current_rubric_ids()


# -- init --resume -------------------------------------------------------------------------------------------------------

def test_init_resume_writes_the_drafted_settings_where_the_scan_reads_them(workdir, monkeypatch, capsys):
    fake = FakeGemini()
    config = _init_with(workdir, monkeypatch, fake)
    cand = config["candidate"]
    assert cand["name"] == "Asha Rao" and cand["resume_path"] == "asha.md" and cand["rubric_file"] == "rubric.md"
    assert cand["profile"].startswith("6 YOE Java")
    rules = prefilter.configure_titles(config)                      # what run_scan does first
    assert prefilter.title_is_candidate("Senior Java Developer") and not prefilter.title_is_candidate("Principal Engineer")
    assert rules.exceptions == prefilter.DEFAULT_TITLE_EXCEPTIONS
    assert llm_utils.configure_rubric(config) == "rubric.md" and "~6 years" in llm_utils.SCORING_RUBRIC
    out = capsys.readouterr().out
    assert "Asha Rao" in out and "rolesight check-filter" in out and "-test-key-" not in out
    assert [c[3] is onboarding.DRAFT_SCHEMA for c in fake.calls] == [True, False]      # settings, then the rubric
    rubric_prompt = fake.calls[1][2][0]
    years = onboarding.years_of_experience(_draft()["jobs"], __import__("datetime").date.today())
    assert years and years > 6 and f"about {years:g} years" in rubric_prompt and f"Today is {__import__('datetime').date.today().isoformat()}" in rubric_prompt
    assert f"experience:    {years:g} years" in out and "Senior Developer at PayCo" in out


def test_an_exclude_word_inside_the_persons_own_include_words_is_removed(workdir, monkeypatch, capsys):
    config = _init_with(workdir, monkeypatch, FakeGemini(_draft(exclude=["java", "principal"])))
    assert config["candidate"]["titles"]["exclude"] == ["principal"]
    assert "removed from exclude" in capsys.readouterr().out


def test_entries_with_odd_characters_are_dropped_and_reported(workdir, monkeypatch, capsys):
    config = _init_with(workdir, monkeypatch, FakeGemini(_draft(include=["java developer", "c/c++ <dev>", "API"])))
    assert config["candidate"]["titles"]["include"] == ["java developer", "api"]
    assert "c/c++ <dev>" in capsys.readouterr().out


def test_a_drafted_rubric_that_changed_the_rules_is_replaced_by_the_built_in_one(workdir, monkeypatch, capsys):
    broken = DEFAULT_SCORING_RUBRIC.replace("3. Seniority Gap Cap (score <= 50):", "3. Seniority Gap Cap (score <= 70):")
    _init_with(workdir, monkeypatch, FakeGemini(_draft(rubric=broken)))
    assert (workdir / "rubric.md").read_text().strip() == DEFAULT_SCORING_RUBRIC
    assert "changed the rules themselves" in capsys.readouterr().out


def test_a_pdf_resume_is_transcribed_to_markdown_first(workdir, monkeypatch):
    fake = FakeGemini()
    config = _init_with(workdir, monkeypatch, fake, resume_name="Asha Rao CV.pdf")
    assert config["candidate"]["resume_path"] == "resume/Asha_Rao_CV.md"
    assert (workdir / "resume" / "Asha_Rao_CV.md").read_text().startswith("# Asha Rao")
    assert isinstance(fake.calls[0][2][0], bytes) and fake.calls[0][3] is None      # the PDF bytes, plain-text answer
    assert "Java developer." in fake.calls[1][2][0]                                 # the draft reads the transcription
    assert len(fake.calls) == 3


def test_existing_personal_settings_are_not_replaced_without_yes(workdir, monkeypatch):
    _init_with(workdir, monkeypatch, FakeGemini())
    before = (workdir / "config.json").read_text()
    with pytest.raises(SystemExit, match="--yes"):
        onboarding.personalize(workdir, workdir / "asha.md", False, False, generate=FakeGemini(_draft(name="Someone Else")))
    assert (workdir / "config.json").read_text() == before


def test_with_yes_the_old_files_are_kept_as_bak(workdir, monkeypatch):
    _init_with(workdir, monkeypatch, FakeGemini())
    first = (workdir / "config.json").read_text()
    onboarding.personalize(workdir, workdir / "asha.md", False, True, generate=FakeGemini(_draft(name="Asha R.")))
    assert (workdir / "config.json.bak").read_text() == first
    assert json.loads((workdir / "config.json").read_text())["candidate"]["name"] == "Asha R."


def test_without_a_key_init_says_where_to_put_it_and_calls_nothing(workdir, monkeypatch):
    fake = FakeGemini()
    with pytest.raises(SystemExit, match="aistudio.google.com"):
        _init_with(workdir, monkeypatch, fake, key=None)
    assert fake.calls == [] and (workdir / "config.json").exists()


def test_the_key_typed_on_a_terminal_is_saved_to_env(workdir, monkeypatch):
    onboarding._scaffold(workdir)
    monkeypatch.setattr(onboarding.sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(onboarding.getpass, "getpass", lambda prompt: "AIza" + "-typed-key-0123456789")
    assert onboarding._api_key(workdir) == "AIza" + "-typed-key-0123456789"
    assert 'GEMINI_API_KEY="' + "AIza" + '-typed-key-0123456789"' in (workdir / ".env").read_text()


def test_a_resume_of_another_format_is_refused(workdir):
    (workdir / "cv.docx").write_text("x")
    with pytest.raises(SystemExit, match="pdf, .md or .txt"):
        onboarding.personalize(workdir, workdir / "cv.docx", True, False, generate=FakeGemini())


def test_init_flags_reach_init_project(monkeypatch):
    seen = {}
    monkeypatch.setattr(main, "init_project", lambda **kw: seen.update(kw))
    monkeypatch.setattr(sys, "argv", ["rolesight", "init", "--resume", "cv.pdf", "--yes"])
    main.main()
    assert seen == {"resume": "cv.pdf", "yes": True}


# -- check-filter and the scan ---------------------------------------------------------------------------------------------

def test_check_filter_uses_the_config_json_filter(workdir, capsys):
    (workdir / "config.json").write_text(json.dumps({"candidate": {"titles": {"include": ["java developer"]}, "cities": ["Pune"]}}))
    onboarding.check_filter_command(["Java Developer", "Pune, India"])
    onboarding.check_filter_command(["Java Developer", "Chennai, India"])
    printed = capsys.readouterr()
    assert printed.out.splitlines()[0] == "KEPT" and "not in your cities (Pune)" in printed.out
    assert printed.err.count("config.json candidate.titles") == 2          # which filter: on stderr, stdout stays one line


def test_check_filter_without_a_config_uses_the_defaults(workdir, capsys):
    onboarding.check_filter_command(["Java Developer", "Pune, India"])
    assert "REJECTED — Title matched exclude pattern: 'Java'" in capsys.readouterr().out


def test_a_scan_with_a_broken_titles_block_stops_before_fetching(monkeypatch, tmp_path):
    from job_hunt import scanner
    monkeypatch.chdir(tmp_path)
    fetched = []
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda *a, **k: fetched.append(1) or [])
    with pytest.raises(SystemExit, match="config.json: candidate.titles"):
        scanner.run_scan({"candidate": {"titles": {"include": []}}}, [{"name": "x", "ats": "greenhouse", "slug": "x"}])
    assert fetched == []


# -- found by running `init --resume` for real: a key exported in the shell, and the .env template next to it -------------

def test_a_placeholder_in_env_does_not_hide_a_key_exported_in_the_shell(workdir, monkeypatch):
    onboarding._scaffold(workdir)                              # writes .env with GEMINI_API_KEY="your_gemini_api_key_here"
    monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "-shell-key-0123456789")
    assert onboarding._api_key(workdir) == "AIza" + "-shell-key-0123456789"


def test_a_scan_reads_the_shell_key_when_env_has_only_the_placeholder(workdir, monkeypatch):
    onboarding._scaffold(workdir)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "-shell-key-0123456789")
    assert main.load_config()["gemini_api_key"] == "AIza" + "-shell-key-0123456789"


def test_a_real_value_in_env_still_beats_the_shell(workdir, monkeypatch):
    onboarding._scaffold(workdir)
    (workdir / ".env").write_text('GEMINI_API_KEY="' + "AIza" + '-env-file-key-0123456789"\n')
    monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "-shell-key-0123456789")
    assert main.load_config()["gemini_api_key"] == "AIza" + "-env-file-key-0123456789"


def test_a_bare_engineer_include_word_is_dropped(workdir, monkeypatch, capsys):
    config = _init_with(workdir, monkeypatch, FakeGemini(_draft(include=["engineer", "java developer"])))
    assert config["candidate"]["titles"]["include"] == ["java developer"]
    assert "nearly every title" in capsys.readouterr().out


def test_cosmetic_changes_around_an_unchanged_heading_are_accepted():
    bolded = DEFAULT_SCORING_RUBRIC.replace("3. Seniority Gap Cap (score <= 50):", "  **3. Seniority Gap Cap (score <= 50):**")
    assert onboarding.rubric_problems(onboarding.normalise_rubric("```\n" + bolded + "\n```")) == []


def test_a_rubric_flattened_onto_one_line_falls_back_to_the_built_in_one():
    """What Gemini returned on 2026-10-14 when the rubric was a JSON field: the right words on one line."""
    settings, notes = onboarding.clean_draft(_draft(rubric=" ".join(DEFAULT_SCORING_RUBRIC.split())))
    assert settings["rubric"] == DEFAULT_SCORING_RUBRIC and any("changed the rules" in n for n in notes)


def test_without_years_no_rubric_is_drafted(workdir, monkeypatch):
    fake = FakeGemini(_draft(jobs=[{"company": "x", "start": "sometime", "end": "later"}]))
    _init_with(workdir, monkeypatch, fake)
    assert len(fake.calls) == 1 and (workdir / "rubric.md").read_text().strip() == DEFAULT_SCORING_RUBRIC


def test_years_are_counted_from_the_job_dates_overlaps_once():
    from datetime import date
    today = date(2026, 10, 14)
    manish = [{"company": "AIQoD", "start": "2023-11", "end": "present"}, {"company": "Microsoft", "start": "2021-10", "end": "2022-01"}]
    assert onboarding.years_of_experience(manish, today) == 3.3          # 36 + 4 months; his resume says "3.3+ years"
    overlap = [{"start": "2020-01", "end": "2020-12"}, {"start": "2020-07", "end": "2021-06"}]
    assert onboarding.years_of_experience(overlap, today) == 1.5
    assert onboarding.years_of_experience([{"start": "2027-01", "end": "present"}, {"start": "x", "end": "2020-01"}], today) is None

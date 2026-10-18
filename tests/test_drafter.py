"""Drafter: the job description comes from the database (or --jd-file); the LLM is mocked; never submits."""

import pytest

from job_hunt import drafter
from job_hunt.db import init_db, save_job
from job_hunt.models import JobPosting

URL = "https://acme.co/jobs/mle"


@pytest.fixture
def draft_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume").mkdir()
    (tmp_path / "resume" / "r.md").write_text("Ada Lovelace — ML engineer, 10 YOE.")
    init_db(str(tmp_path / "data" / "jobs.db"))
    save_job(JobPosting(global_id="greenhouse:acme:1", ats="greenhouse", company="Acme Co", title="MLE",
                        location="Bengaluru, India", is_remote=False, url=URL,
                        description_text="Job description body"), status="discovered")
    monkeypatch.setattr(drafter, "chat_with_llm", lambda config, messages, **k: "LLM OUTPUT")
    return {"candidate": {"name": "Ada", "resume_path": "resume/r.md"}}   # no TinyFish key anywhere


def test_draft_from_url_writes_three_files_named_after_the_company(draft_env):
    drafter.draft_application(draft_env, URL)
    from pathlib import Path
    out_dirs = list(Path("output/drafts").glob("acme_co-*"))
    assert out_dirs
    files = {p.name for p in out_dirs[0].iterdir()}
    assert any(f.startswith("resume_") for f in files)
    assert any(f.startswith("cover_letter_") for f in files)
    assert "application_info.txt" in files


def test_draft_needs_no_tinyfish(draft_env):
    """The module no longer imports TinyFish, and no key is read (T40)."""
    assert not hasattr(drafter, "TinyFish")
    drafter.draft_application(draft_env, URL)


def test_the_prompts_carry_the_stored_description_untruncated(draft_env, monkeypatch):
    long_jd = "Intro. " * 1500 + "REQUIREMENTS_AT_THE_END"
    save_job(JobPosting(global_id="greenhouse:acme:2", ats="greenhouse", company="Acme Co", title="Long",
                        location="Pune", is_remote=False, url="https://acme.co/jobs/long",
                        description_text=long_jd), status="discovered")
    prompts = []
    monkeypatch.setattr(drafter, "chat_with_llm", lambda config, messages, **k: prompts.append(messages[0]["content"]) or "OUT")
    drafter.draft_application(draft_env, "https://acme.co/jobs/long")
    assert len(long_jd) > 4000 and all("REQUIREMENTS_AT_THE_END" in p for p in prompts)


def test_unknown_url_explains_what_to_do(draft_env):
    with pytest.raises(RuntimeError, match="not in the database") as ei:
        drafter.draft_application(draft_env, "https://other.co/jobs/9")
    assert "--jd-file" in str(ei.value)


def test_job_scanned_before_descriptions_were_stored_explains_it(draft_env, monkeypatch):
    save_job(JobPosting(global_id="greenhouse:acme:3", ats="greenhouse", company="Acme Co", title="Old",
                        location="Pune", is_remote=False, url="https://acme.co/jobs/old", description_text=""),
             status="discovered")
    with pytest.raises(RuntimeError, match="no stored description"):
        drafter.draft_application(draft_env, "https://acme.co/jobs/old")


def test_jd_file_replaces_the_database(draft_env, tmp_path, monkeypatch):
    jd = tmp_path / "jd.txt"
    jd.write_text("Pasted job description about Kafka")
    prompts = []
    monkeypatch.setattr(drafter, "chat_with_llm", lambda config, messages, **k: prompts.append(messages[0]["content"]) or "OUT")
    drafter.draft_application(draft_env, "https://unknown.co/jobs/1", jd_file=str(jd))
    assert all("Pasted job description about Kafka" in p for p in prompts)


def _completed_scan(rows):
    """data/jobs.db after one completed scan that scored `rows` (url, company, title, score), in that order (T31)."""
    from job_hunt.db import finish_scan, init_db, save_job, start_scan, update_job_status
    from job_hunt.models import JobPosting, job_key
    init_db("data/jobs.db")
    sid = start_scan()
    for url, company, title, score in rows:
        j = JobPosting(global_id=url, ats="greenhouse", company=company, title=title, location="Bengaluru",
                       is_remote=False, url=url)
        save_job(j)
        update_job_status(job_key(j), "scored", score, "r")
    finish_scan(sid)


def test_resolve_job_by_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _completed_scan([("https://acme.co/jobs/1", "Acme Co", "MLE", 80)])
    url, slug = drafter._resolve_job("#1")
    assert url == "https://acme.co/jobs/1" and slug == "acme_co"


def test_resolve_job_out_of_range(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _completed_scan([])
    with pytest.raises(ValueError):
        drafter._resolve_job("#3")


def test_resolve_job_no_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        drafter._resolve_job("#1")


def test_slug():
    assert drafter._slug("Acme Co, Inc.") == "acme_co_inc"


def test_cover_letter_prompt_gets_the_whole_resume(draft_env, monkeypatch, tmp_path):
    """T14: the cover-letter prompt used resume[:2500], cutting the Projects/Education the scorer sees."""
    long_resume = "Experience line.\n" * 300 + "END_OF_RESUME_MARKER"
    assert len(long_resume) > 2500
    (tmp_path / "resume" / "r.md").write_text(long_resume)
    prompts = []
    monkeypatch.setattr(drafter, "chat_with_llm", lambda config, messages, **k: prompts.append(messages[0]["content"]) or "OUT")
    drafter.draft_application(draft_env, URL)
    cover = next(p for p in prompts if "cover letter" in p)
    assert "END_OF_RESUME_MARKER" in cover

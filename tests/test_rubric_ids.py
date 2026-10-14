"""T97: scripts/rubric_ids.py decodes the ids stored in `jobs.score_rubric` (real git in a temp repo; no network)."""
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

from job_hunt import llm_utils
from job_hunt.db import connect, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("rubric_ids", ROOT / "scripts" / "rubric_ids.py")
rubric_ids = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rubric_ids)


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=repo, check=True,
                   capture_output=True)


def _commit_rubric(repo, rubric, note):
    (repo / "job_hunt").mkdir(exist_ok=True)
    (repo / "job_hunt" / "llm_utils.py").write_text(f'# {note}\nSCORING_RUBRIC = """{rubric}"""\nOTHER = 1\n')
    _git(repo, "add", "job_hunt/llm_utils.py")
    _git(repo, "commit", "-q", "-m", note)


def _job(i):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js")


def test_versions_lists_each_distinct_rubric_once_oldest_first(tmp_path):
    _git(tmp_path, "init", "-q")
    _commit_rubric(tmp_path, "rule one", "T1: first rubric")
    _commit_rubric(tmp_path, "rule one", "T2: comment only, same rubric")
    _commit_rubric(tmp_path, "rule one and two", "T3: second rubric")
    versions = rubric_ids.rubric_versions(tmp_path)
    assert [v["id"] for v in versions] == [llm_utils.rubric_id("rule one"), llm_utils.rubric_id("rule one and two")]
    assert [v["subject"] for v in versions] == ["T1: first rubric", "T3: second rubric"]   # the first commit of each
    assert [v["chars"] for v in versions] == [len("rule one"), len("rule one and two")]
    assert all(len(v["commit"]) >= 7 and v["date"] for v in versions)


def test_a_commit_that_predates_the_rubric_or_does_not_parse_is_skipped(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "job_hunt").mkdir()
    (tmp_path / "job_hunt" / "llm_utils.py").write_text("X = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "no rubric yet")
    (tmp_path / "job_hunt" / "llm_utils.py").write_text("def broken(:\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "syntax error")
    _commit_rubric(tmp_path, "only one", "T3: first real rubric")
    assert [v["id"] for v in rubric_ids.rubric_versions(tmp_path)] == [llm_utils.rubric_id("only one")]


def test_counts_group_the_scored_rows_by_id_and_leave_the_unscored_out(tmp_path):
    db = str(tmp_path / "jobs.db")
    for i in (1, 2, 3, 4):
        save_job(_job(i), db_path=db)
    update_job_status(job_key(_job(1)), "scored", 80, "r", db_path=db, rubric="aaaaaaaa")
    update_job_status(job_key(_job(2)), "notified", 90, "r", db_path=db, rubric="aaaaaaaa")
    update_job_status(job_key(_job(3)), "scored", 70, "r", db_path=db)                       # scored before T97
    assert rubric_ids.counts_by_rubric(db) == {"aaaaaaaa": 2, None: 1}                       # job 4 is only 'discovered'


def test_the_script_names_the_checkouts_own_id_and_the_database_counts(tmp_path):
    db = str(tmp_path / "jobs.db")
    init_db(db)
    save_job(_job(1), db_path=db)
    update_job_status(job_key(_job(1)), "scored", 80, "r", db_path=db, rubric=llm_utils.rubric_id())
    out = subprocess.run(["python", str(ROOT / "scripts" / "rubric_ids.py"), "--db", db], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    assert f"This checkout: {llm_utils.rubric_id()}" in out
    assert f"{llm_utils.rubric_id()}  1 scored" in out and "(current)" in out
    with connect(db) as con:                                           # read-only: nothing was written
        assert con.execute("select count(*) from jobs").fetchone() == (1,)


def test_in_this_repository_every_rubric_in_history_has_an_id():
    """The real consumer: this repo's own git history (a shallow clone has at least the commit it has)."""
    if subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT, capture_output=True).returncode != 0:
        pytest.skip("not a git checkout")
    versions = rubric_ids.rubric_versions(ROOT)
    assert versions and all(re.fullmatch(r"[0-9a-f]{8}", v["id"]) for v in versions)

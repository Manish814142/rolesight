"""T97: which scoring rubric is which id, and how many stored scores carry each.

    python scripts/rubric_ids.py                  # every distinct SCORING_RUBRIC in the git history, oldest first
    python scripts/rubric_ids.py --db data/jobs.db   # also the scored rows of the database, by id

`jobs.score_rubric` holds `llm_utils.rubric_id()`: 8 hex digits of the SHA-256 of the rubric text. The id says nothing by
itself; this prints the commit that first had that text. A scored row with no id ("-") was scored before ids were
recorded (T97, 2026-10-14): its `scored_at` against the commit dates below tells which rubric it most likely met.
Read-only: nothing is written.
"""
from __future__ import annotations

import argparse
import ast
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.llm_utils import rubric_id  # noqa: E402

SOURCE = "job_hunt/llm_utils.py"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else ""


def _rubric_at(repo: Path, commit: str) -> Optional[str]:
    """The SCORING_RUBRIC string of `job_hunt/llm_utils.py` at `commit`; None if the file has none or does not parse."""
    try:
        tree = ast.parse(_git(repo, "show", f"{commit}:{SOURCE}"))
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "SCORING_RUBRIC" for t in node.targets):
            value = ast.literal_eval(node.value)
            return value if isinstance(value, str) else None
    return None


def rubric_versions(repo: Path) -> List[Dict[str, object]]:
    """Each distinct rubric text in the history of llm_utils.py, once, at the commit that first had it, oldest first."""
    log = _git(repo, "log", "--reverse", "--date=short", "--format=%h%x09%ad%x09%s", "--", SOURCE)
    seen, out = set(), []
    for line in log.splitlines():
        commit, date, subject = line.split("\t", 2)
        text = _rubric_at(repo, commit)
        if text is None or rubric_id(text) in seen:
            continue
        seen.add(rubric_id(text))
        out.append({"id": rubric_id(text), "chars": len(text), "commit": commit, "date": date, "subject": subject})
    return out


def counts_by_rubric(db_path: str) -> Dict[Optional[str], int]:
    """Scored rows (status scored or notified) by `score_rubric`; None = scored before the id was recorded."""
    conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    try:
        have = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        column = "score_rubric" if "score_rubric" in have else "NULL"
        rows = conn.execute(f"SELECT {column}, COUNT(*) FROM jobs WHERE status IN ('scored', 'notified') "
                            f"AND score IS NOT NULL GROUP BY 1").fetchall()
    finally:
        conn.close()
    return {rubric: n for rubric, n in rows}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Decode the rubric ids stored with scores (T97).")
    parser.add_argument("--db", help="also count this database's scored rows by rubric id (opened read-only)")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    print(f"This checkout: {rubric_id()}")
    from job_hunt.onboarding import (
        use_rubric_of_config_file,  # T106: config.json's rubric_file, if any, is the current one
    )
    source = use_rubric_of_config_file()
    current = rubric_id()
    if source != "built-in":
        print(f"Your rubric ({source}): {current}")
    print("\nRubric versions in the git history (first commit of each):")
    for v in rubric_versions(repo):
        mark = "  (current)" if v["id"] == current else ""
        print(f"  {v['id']}  {v['chars']:>5} chars  {v['commit']}  {v['date']}  {str(v['subject'])[:70]}{mark}")
    if args.db:
        print(f"\nScored rows in {args.db}:")
        for rubric, n in sorted(counts_by_rubric(args.db).items(), key=lambda kv: (kv[0] is None, kv[0] or "")):
            mark = "  (current)" if rubric == current else ""
            print(f"  {rubric or '-':<8}  {n} scored{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

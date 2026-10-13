#!/usr/bin/env python3
"""One-time import of scored jobs that only the retired JSON state files hold (T34).

Until T34 every scan also wrote state/last_scan.json and state/job_history.json; `export` and `draft N` read them.
Since T31/T32/T34 everything reads data/jobs.db, so a job that is in those files but not in the database would vanish
from `export --days N`. On 2026-10-08 that was 40 of the 176 URLs in the production job_history.json (15 of them
scored >= 70): they were scored before data/jobs.db was cleared on 2026-10-04.

    python scripts/import_json_history.py             # dry run: prints what it would import, writes nothing
    python scripts/import_json_history.py --apply     # import
    python scripts/import_json_history.py --dir /path/to/workdir --apply

Only URLs the database does not know at all are imported, as `scored` rows with the JSON score and reason,
scored_at = the scan date (00:00 UTC), ats `import` and global_id `import:<url hash>`; score_model stays NULL (unknown). A URL already in the database is never
touched, whatever its status: the database's own score is newer. Running it twice imports nothing the second time.
The JSON files are only read; delete them yourself once you are happy with the result.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.db import init_db  # noqa: E402
from job_hunt.models import canonical_hash, url_hash  # noqa: E402

STATE_FILES = ("job_history.json", "last_scan.json")   # job_history first: it is the cumulative one


def _entries(state_dir: Path) -> list[dict]:
    """Scored entries of the JSON files, one per URL (the first file that has it wins)."""
    seen: dict[str, dict] = {}
    for name in STATE_FILES:
        f = state_dir / name
        if not f.exists():
            continue
        for e in json.loads(f.read_text(encoding="utf-8")):
            if isinstance(e, dict) and e.get("url") and isinstance(e.get("score"), int) and e["url"] not in seen:
                seen[e["url"]] = e
    return list(seen.values())


def import_history(workdir: Path, apply: bool) -> dict[str, int]:
    db_path = workdir / "data" / "jobs.db"
    if not db_path.exists():
        sys.exit(f"No database at {db_path}")
    if apply:
        init_db(str(db_path))          # brings an older database up to the current schema first
    counts = {"in_files": 0, "already_in_db": 0, "imported": 0, "duplicate_title": 0}
    entries = _entries(workdir / "state")
    counts["in_files"] = len(entries)
    # A dry run opens the database read-only: not even the schema is migrated.
    with closing(sqlite3.connect(str(db_path) if apply else f"file:{db_path}?mode=ro", uri=not apply)) as conn:
        for e in entries:
            if conn.execute("SELECT 1 FROM jobs WHERE url_hash = ? LIMIT 1;", (url_hash(e["url"]),)).fetchone():
                counts["already_in_db"] += 1
                continue
            day = str(e.get("scan_date") or "")[:10]
            title = e.get("extracted_title") or e.get("title") or ""
            location = e.get("location") or ""
            if not apply:
                counts["imported"] += 1
                continue
            try:
                conn.execute(
                    "INSERT INTO jobs (canonical_hash, url_hash, global_id, title, company, ats, url, score, "
                    "score_reason, status, discovered_at, scored_at, location, posted_at, description) "
                    "VALUES (?, ?, ?, ?, ?, 'import', ?, ?, ?, 'scored', ?, ?, ?, ?, '');",
                    # Own key per URL: with no ATS id the row would fall back to the unique canonical_hash (title +
                    # company + location), and two openings with the same title (13 on the production data) collide.
                    (canonical_hash(title, e.get("company") or "", location), url_hash(e["url"]),
                     f"import:{url_hash(e['url'])}", title,
                     e.get("company") or "", e["url"], int(e["score"]), e.get("reason") or "",
                     f"{day}T00:00:00+00:00" if day else None, f"{day}T00:00:00+00:00" if day else None,
                     location, e.get("posted_at") or ""))
                counts["imported"] += 1
            except sqlite3.IntegrityError:      # cannot happen with the per-URL key; counted, never fatal
                counts["duplicate_title"] += 1
        conn.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default=".", help="working directory holding data/ and state/ (default: .)")
    ap.add_argument("--apply", action="store_true", help="write to data/jobs.db (default: dry run)")
    args = ap.parse_args(argv)
    c = import_history(Path(args.dir), args.apply)
    verb = "imported" if args.apply else "would import"
    print(f"{c['in_files']} scored job(s) in the JSON files: {c['already_in_db']} already in data/jobs.db, "
          f"{verb} {c['imported']}" + (f", {c['duplicate_title']} skipped (key already taken)"
                                      if c["duplicate_title"] else "")
          + ("" if args.apply else " (dry run: nothing written; add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

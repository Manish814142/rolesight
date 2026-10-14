"""T69(g), T96: which India jobs does the title rule still drop only for lacking an include word?

    python scripts/measure_prefilter.py --save data/fetch.json            # one full fetch, ~7 min, no Gemini calls
    python scripts/measure_generic_titles.py --jobs data/fetch.json [--days 7] [--top 15]

Before T96 this showed the generic titles the filter dropped ("Senior Engineer", "Engineer II": 26 jobs, 3 in the last 7 days on
2026-10-13); those now reach Gemini, so what is left are titles that name some other role. A job is counted when its location passes
the pre-filter's location rules, its title matches no exclude word and the title rule (include words, generic engineer titles)
rejects it, in one of these kinds:
  qualified  contains the word "engineer" with something else: "Cloud Engineer", "Data Engineer", "Hardware Engineer"
  other      no "engineer" at all ("Analyst", "Scientist", "Consultant", ...)
The company only groups the report; it never decides anything (the filter itself never reads it).
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.models import JobPosting  # noqa: E402
from job_hunt.prefilter import (  # noqa: E402
    posted_age_days,
    should_evaluate_job,
    title_exclusions,
    title_is_candidate,
)

ENGINEER = re.compile(r"\bengineer(s|ing)?\b", re.IGNORECASE)


def _job(row: Dict[str, Any], title: str) -> JobPosting:
    return JobPosting(global_id="x", ats=row.get("ats", ""), company=row.get("company", ""), title=title,
                      location=row.get("location", ""), is_remote=bool(row.get("is_remote")), url=row.get("url", ""))


def kind(row: Dict[str, Any]) -> str | None:
    """"qualified" or "other" for a job dropped only for lacking an include word in an India location; None otherwise."""
    title = row["title"]
    if title_is_candidate(title) or title_exclusions(title):
        return None
    if not should_evaluate_job(_job(row, "Backend Engineer"))[0]:      # the real location rules, with a title that passes
        return None
    return "qualified" if ENGINEER.search(title) else "other"


def analyse(rows: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    survivors_by_company: collections.Counter = collections.Counter()
    dropped: Dict[str, List[Dict[str, Any]]] = {"qualified": [], "other": []}
    for r in rows:
        if should_evaluate_job(_job(r, r["title"]))[0]:
            survivors_by_company[r["company"]] += 1
            continue
        k = kind(r)
        if k:
            dropped[k].append(r)

    def recent(rs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for r in rs:
            age = posted_age_days(r.get("posted_at", ""))
            if age is None or age <= days:                       # undated jobs are kept by the window, as in a scan
                out.append(r)
        return out

    return {"survivors": sum(survivors_by_company.values()), "survivors_by_company": survivors_by_company,
            "dropped": dropped, "recent": {k: recent(v) for k, v in dropped.items()}}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", required=True, help="a saved fetch from measure_prefilter.py --save")
    ap.add_argument("--days", type=int, default=7, help="the posted window to count (default 7, the scan's)")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args(argv)
    rows = json.loads(Path(args.jobs).read_text())
    res = analyse(rows, args.days)
    print(f"{len(rows)} jobs fetched; {res['survivors']} pass the pre-filter today")
    print(f"\nIndia (or remote-from-India) jobs dropped only for lacking an include word, by kind (all / posted within {args.days} days or undated):")
    for k in ("qualified", "other"):
        print(f"  {k:10} {len(res['dropped'][k]):6} {len(res['recent'][k]):6}")
    for k in ("qualified",):
        print(f"\nTop {k} titles (all / recent):")
        titles = collections.Counter(r["title"] for r in res["dropped"][k])
        recent_titles = collections.Counter(r["title"] for r in res["recent"][k])
        for t, n in titles.most_common(args.top):
            print(f"  {n:5} {recent_titles.get(t, 0):5}  {t}")
    print("\nCompanies with the most dropped engineer titles (all / recent; the last column is that company's jobs that pass the filter today):")
    by_co = collections.Counter(r["company"] for r in res["dropped"]["qualified"])
    rec_co = collections.Counter(r["company"] for r in res["recent"]["qualified"])
    for c, n in by_co.most_common(args.top):
        print(f"  {n:5} {rec_co.get(c, 0):5}  {c:32} passing today: {res['survivors_by_company'].get(c, 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

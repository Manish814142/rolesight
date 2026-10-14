"""What does the pre-filter cost and let through? (T17, and a check for any pre-filter change)

    python scripts/measure_prefilter.py --save jobs.json     # fetch every company once (~9 min), save title/location
    python scripts/measure_prefilter.py --jobs jobs.json     # analyse a saved fetch (no network)

Prints the survivors and, for India jobs that name a target role but are rejected by an exclusion word,
how many are blocked ONLY by one language/framework word, and how many of those were posted in the
last 30 days. Titles only; the company field is never used.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.models import JobPosting  # noqa: E402
from job_hunt.prefilter import (  # noqa: E402
    location_is_india,
    posted_age_days,
    should_evaluate_job,
    title_exclusions,
    title_included,
)

WATCH = ("java", "golang", "react", "reactjs", "angular", "angularjs", "vue", "frontend", "front-end")


def _blockers(title: str) -> set:
    return title_exclusions(title)


def survivors(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def job(r: Dict[str, Any]) -> JobPosting:
        return JobPosting(global_id="x", ats=r.get("ats", ""), company=r.get("company", ""), title=r["title"],
                          location=r.get("location", ""), is_remote=bool(r.get("is_remote")), url=r.get("url", ""))
    return [r for r in rows if should_evaluate_job(job(r))[0]]


def exclusion_costs(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """word -> {"only": jobs blocked only by that word, "recent": of those, posted <= 30 days ago}."""
    only: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        if not (location_is_india(r.get("location", "")) and title_included(r["title"])):
            continue
        b = _blockers(r["title"])
        if len(b) == 1 and next(iter(b)) in WATCH:
            only[next(iter(b))].append(r)
    out = {}
    for w, v in only.items():
        ages = [posted_age_days(r.get("posted_at", "")) for r in v]
        out[w] = {"only": len(v), "recent": sum(a is not None and a <= 30 for a in ages)}  # age 0 is today, not unknown
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", help="saved fetch (JSON list of title/location/ats/company/posted_at rows)")
    ap.add_argument("--save", help="fetch every company in companies.json and save the rows here")
    args = ap.parse_args(argv)
    if args.save:
        from job_hunt.scanner import _prefetch_jobs
        companies = json.loads(Path("companies.json").read_text())
        res = _prefetch_jobs(companies, 8)
        rows = [{"company": c["name"], "ats": c["ats"], "title": j.title, "location": j.location, "url": j.url,
                 "posted_at": j.posted_at, "is_remote": j.is_remote} for c, (jobs, _, _) in zip(companies, res) for j in jobs]
        Path(args.save).write_text(json.dumps(rows))
        print(f"saved {len(rows)} jobs to {args.save}")
    elif args.jobs:
        rows = json.loads(Path(args.jobs).read_text())
    else:
        ap.error("give --jobs FILE or --save FILE")
    surv = survivors(rows)
    print(f"{len(rows)} jobs; {len(surv)} pass the pre-filter")
    costs = exclusion_costs(rows)
    print(f"{'word':10} {'only-blocked-by-it':>18} {'of which <=30d':>15}")
    for w in WATCH:
        if w in costs:
            print(f"{w:10} {costs[w]['only']:18} {costs[w]['recent']:15}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

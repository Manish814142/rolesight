#!/usr/bin/env python3
"""Try the pre-filter on one job, e.g. after editing job_hunt/prefilter.py (T80).

    python scripts/check_filter.py "Senior Backend Engineer" "Bengaluru, India"
    python scripts/check_filter.py "Backend Engineer" "" --remote

Prints KEPT (the job would go to Gemini) or REJECTED with the filter's own reason. Local only: no network, no API key.
"""
import argparse

from job_hunt.models import JobPosting
from job_hunt.prefilter import should_evaluate_job


def main() -> None:
    ap = argparse.ArgumentParser(description="Show what the pre-filter does with one job.")
    ap.add_argument("title", help='job title, e.g. "Java Developer"')
    ap.add_argument("location", nargs="?", default="", help='location text as the board shows it, e.g. "Pune, India"')
    ap.add_argument("--remote", action="store_true", help="the board flags the job as remote")
    args = ap.parse_args()
    job = JobPosting(global_id="check:1", ats="check", company="check", title=args.title, location=args.location,
                     is_remote=args.remote, url="https://example.com/check")
    kept, reason = should_evaluate_job(job)
    print("KEPT" if kept else f"REJECTED — {reason}")


if __name__ == "__main__":
    main()

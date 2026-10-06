"""How long does each Workday tenant take, and how many "N Locations" detail calls does it make? (T23)

    python scripts/measure_workday_tenants.py [--workers 8] [--save result.json]

Fetches every Workday company in companies.json exactly as a scan does (fetch_workday, 8 parallel workers)
and prints, slowest first: seconds, jobs fetched, detail calls (one per "N Locations" job) with the time they
took, and how many of those calls went to jobs whose TITLE the pre-filter rejects (the saving a title check
before the detail call would give). Survivors = jobs that pass the whole pre-filter, for a before/after check.
Real network: about what the Workday part of one scan costs.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.adapters import workday  # noqa: E402
from job_hunt.prefilter import should_evaluate_job  # noqa: E402

_lock = threading.Lock()
_detail: Dict[str, List[float]] = {}          # tenant -> seconds of each detail call


def _timed_detail(original):
    def wrapper(cxs_base: str, external_path: str):
        tenant = cxs_base.rstrip("/").split("/")[-2]
        t0 = time.monotonic()
        try:
            return original(cxs_base, external_path)
        finally:
            with _lock:
                _detail.setdefault(tenant, []).append(time.monotonic() - t0)
    return wrapper


def _title_rejected(job) -> bool:
    """True when the pre-filter would reject this job on its title (location neutralised)."""
    probe = dataclasses.replace(job, location="Bengaluru, India", is_remote=False)
    return not should_evaluate_job(probe)[0]


def measure_one(company: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.monotonic()
    error = ""
    try:
        jobs = workday.fetch_workday(company["tenant"], company["dc"], company["site"])
    except Exception as e:  # noqa: BLE001 - a measurement must not stop at one tenant
        jobs, error = [], str(e)
    seconds = time.monotonic() - t0
    detailed = [j for j in jobs if j.description_text]          # only detail calls fill the description at fetch time
    calls = _detail.get(company["tenant"], [])
    return {
        "name": company["name"], "seconds": round(seconds, 1), "jobs": len(jobs),
        "detail_calls": len(calls), "detail_seconds": round(sum(calls), 1),
        "detail_calls_on_title_rejected": sum(_title_rejected(j) for j in detailed),
        "survivors": sum(should_evaluate_job(j)[0] for j in jobs), "error": error,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--save", help="write the per-tenant rows here as JSON")
    args = ap.parse_args(argv)

    companies = [c for c in json.loads(Path("companies.json").read_text()) if c.get("ats") == "workday"]
    workday._fetch_detail = _timed_detail(workday._fetch_detail)      # type: ignore[assignment]
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        rows = list(ex.map(measure_one, companies))
    wall = time.monotonic() - t0

    rows.sort(key=lambda r: r["seconds"], reverse=True)
    print(f"{'tenant':28} {'sec':>7} {'jobs':>6} {'detail':>7} {'det.sec':>8} {'on rejected title':>18} {'survivors':>10}")
    for r in rows:
        print(f"{r['name'][:28]:28} {r['seconds']:7.1f} {r['jobs']:6d} {r['detail_calls']:7d} {r['detail_seconds']:8.1f} "
              f"{r['detail_calls_on_title_rejected']:18d} {r['survivors']:10d}" + (f"  ERROR {r['error'][:40]}" if r["error"] else ""))
    slow = [r["name"] for r in rows if r["seconds"] > 60]
    print(f"\n{len(rows)} tenants, {wall:.0f} s wall clock with {args.workers} workers; "
          f"jobs {sum(r['jobs'] for r in rows)}, survivors {sum(r['survivors'] for r in rows)}, "
          f"detail calls {sum(r['detail_calls'] for r in rows)} "
          f"({sum(r['detail_calls_on_title_rejected'] for r in rows)} on a title the pre-filter rejects)")
    print(f"tenants over 60 s: {len(slow)} {slow}")
    if args.save:
        Path(args.save).write_text(json.dumps(rows, indent=1))
        print(f"saved to {args.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

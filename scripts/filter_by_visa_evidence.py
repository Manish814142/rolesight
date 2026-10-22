#!/usr/bin/env python3
"""Keep only the companies that show evidence of sponsoring visas (T144, Manish 2026-10-22: "if they sponsor a visa then keep
them, irrespective of a specific job post ... otherwise no point of adding them").

    python scripts/filter_by_visa_evidence.py --candidates /tmp/v1.json /tmp/v2.json --out /tmp/kept.json --report /tmp/f.csv \\
        [--postings /tmp/posting_evidence.json]

Reads the entries `autopilot discover` verified (companies.json format) and keeps one when, for a country it hires in:
  - it is on that country's sponsor record (UK register, Dutch IND register, Irish permits, US H-1B, Canadian LMIA), by an exact or
    "squashed" name match or a loose one accepted in scripts/visa_sponsor_review.json (build_visa_sponsors.py's rules), or
  - it is on a community list for that country, or
  - one of its postings offers visa sponsorship (`--postings`: {company: {"visa": {"offered": n}}}, from a fetch of its jobs).
A Workday entry records every country checked, so any record counts for it. Loose matches nobody has reviewed are not evidence:
the report lists them under `review` so they can be accepted or rejected in the review file, then run again.
The registers are read from data/visa_sources/ (build_visa_sponsors.py downloads them). Employers on no record, in countries that
publish none (Germany, France, Spain ...), are dropped unless a posting says so: that is the cost of the rule.
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_visa_sponsors as bvs  # noqa: E402

from job_hunt.visa import _list_covers  # noqa: E402

REGISTER_COUNTRY = {"uk": "United Kingdom", "nl": "Netherlands", "ie": "Ireland", "us": "United States", "ca": "Canada"}


def judge(entry: Dict[str, Any], indexes: Dict[str, "bvs.Index"], review: Dict[str, Dict[str, List[str]]],
          postings: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
    """("keep" | "review" | "drop", the evidence, the weak matches nobody has reviewed)."""
    name, places = entry["name"], set(entry.get("places") or [])
    evidence: List[str] = []
    weak: List[str] = []
    for source, index in indexes.items():
        kind, names = index.match(name)
        if not kind:
            continue
        for source_name in names:
            verdict = bvs.status(name, source_name, kind, review)
            if verdict == "unreviewed":
                weak.append(f"{source}: {source_name}")
            elif verdict == "kept":
                where = REGISTER_COUNTRY.get(source)
                if source == "lists":
                    details = index.entries[source_name]
                    relevant = entry["ats"] == "workday" or any(_list_covers(details, c) for c in places)
                else:
                    relevant = entry["ats"] == "workday" or where in places
                if relevant:
                    evidence.append(f"{source}: {source_name}")
    if postings.get(name, {}).get("visa", {}).get("offered", 0) > 0:
        evidence.append("posting offers visa sponsorship")
    return ("keep" if evidence else "review" if weak else "drop"), evidence, weak


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", nargs="+", required=True, help="verified entries (discover --out files)")
    ap.add_argument("--out", required=True, help="the entries that pass, companies.json format")
    ap.add_argument("--report", help="CSV: every candidate with its decision, evidence and unreviewed weak matches")
    ap.add_argument("--postings", help="JSON of posting wording per company (optional)")
    ap.add_argument("--sources", default="data/visa_sources", help="the downloads of build_visa_sponsors.py")
    ap.add_argument("--review", default=str(Path(__file__).resolve().parent / "visa_sponsor_review.json"))
    args = ap.parse_args(argv)
    src = Path(args.sources)
    if not (src / "sources.json").exists():
        sys.exit(f"filter_by_visa_evidence: nothing downloaded in {src} yet; run build_visa_sponsors.py first")
    indexes = bvs.load_sources(src)
    review = bvs.load_review(Path(args.review))
    postings = json.loads(Path(args.postings).read_text(encoding="utf-8")) if args.postings else {}
    entries: List[Dict[str, Any]] = []
    for f in args.candidates:
        entries += json.loads(Path(f).read_text(encoding="utf-8"))
    kept: List[Dict[str, Any]] = []
    rows: List[List[str]] = []
    counts = {"keep": 0, "review": 0, "drop": 0}
    for e in entries:
        decision, evidence, weak = judge(e, indexes, review, postings)
        counts[decision] += 1
        if decision == "keep":
            kept.append(e)
        rows.append([decision, e["name"], e["ats"], "; ".join(e.get("places") or ["(all checked)"]), " | ".join(evidence), " | ".join(weak)])
    Path(args.out).write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Decision", "Company", "ATS", "Places", "Evidence", "Weak matches (unreviewed)"])
            rows.sort(key=lambda row: (row[0], row[1].lower()))
            w.writerows(rows)
    print(f"{len(entries)} candidates: {counts['keep']} kept, {counts['review']} only weakly matched (review them), "
          f"{counts['drop']} dropped -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

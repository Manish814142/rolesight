"""How do job postings outside India word visa sponsorship? (T133, groundwork for T108)

    python scripts/measure_visa_wording.py --save /tmp/visa_fetch.json   # fetch the boards whose list API carries descriptions (3.5 min on 2026-10-21)
    python scripts/measure_visa_wording.py --jobs /tmp/visa_fetch.json [--sample 8]   # analyse a saved fetch (no network)

For jobs in the UK, Germany, the Netherlands, Ireland, the UAE, Singapore, or "Europe/EMEA" with no country, counts how
many descriptions offer visa sponsorship, refuse it, mention it without a clear answer, or say nothing; separately,
relocation help and "must already live here" wording. Each is a regex count: `--sample` prints matched sentences to
read by hand. Greenhouse, Lever, Ashby, Workable, Recruitee and Personio only (their list call carries the
description; SmartRecruiters and the India-searched ATSs need a request per job or return India only).
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.prefilter import title_included  # noqa: E402
from job_hunt.visa import (  # noqa: E402,F401  (the classifier lives in job_hunt/visa.py, T138)
    relocation_wording,
    residence_required,
)
from job_hunt.visa import wording as visa_wording  # noqa: E402

DESCRIBED_ATS = ("greenhouse", "lever", "ashby", "workable", "recruitee", "personio")

# A city that also names a place in the US or Canada counts only when the location names no US/Canada marker.
_NOT_NORTH_AMERICA = re.compile(r"\b((?i:usa|u\.s\.|united states|canada|ontario|massachusetts|alabama|new hampshire|"
                                r"connecticut|ohio|california|virginia)|[A-Z]{2}\s*\d{5})\b|,\s*(MA|AL|NH|CT|OH|CA|VA|PA|ON)\b")
COUNTRIES: Dict[str, re.Pattern] = {
    "UK": re.compile(r"\b(united kingdom|u\.?k\.?|england|scotland|wales|great britain|northern ireland|london|"
                     r"manchester|edinburgh|glasgow|cambridge|oxford|bristol|birmingham|leeds|belfast|reading)\b", re.I),
    "Germany": re.compile(r"\b(germany|deutschland|berlin|munich|m(ü|ue|u)nchen|hamburg|frankfurt|cologne|k(ö|oe|o)ln|"
                          r"stuttgart|d(ü|ue|u)sseldorf|leipzig|dresden|nuremberg|n(ü|ue|u)rnberg|karlsruhe|bonn|hannover|hanover)\b", re.I),
    "Netherlands": re.compile(r"\b(netherlands|nederland|holland|amsterdam|rotterdam|utrecht|eindhoven|the hague|den haag|"
                              r"delft|leiden|groningen|haarlem)\b", re.I),
    "Ireland": re.compile(r"(?<!northern )\b(ireland|dublin|cork|galway|limerick)\b", re.I),
    "UAE": re.compile(r"\b(united arab emirates|u\.?a\.?e\.?|dubai|abu dhabi|sharjah)\b", re.I),
    "Singapore": re.compile(r"\bsingapore\b", re.I),
}
COUNTRY_NAMES: Dict[str, re.Pattern] = {
    "UK": re.compile(r"\b(united kingdom|u\.?k\.?|england|scotland|wales|great britain|northern ireland)\b", re.I),
    "Germany": re.compile(r"\b(germany|deutschland)\b", re.I),
    "Ireland": re.compile(r"(?<!northern )\bireland\b", re.I),
}
EUROPE_REGION = re.compile(r"\b(europe|european union|eu|emea|eea)\b", re.I)



def countries(location: str) -> List[str]:
    """The target countries a location names; ["Europe"] when it names only the region; [] otherwise."""
    loc = location or ""
    found = [c for c, rx in COUNTRIES.items() if rx.search(loc)]
    if found and _NOT_NORTH_AMERICA.search(loc):   # "London, Ontario", "Dublin, OH": only the country's own name counts
        found = [c for c in found if c in ("UAE", "Singapore", "Netherlands") or COUNTRY_NAMES[c].search(loc)]
    if not found and EUROPE_REGION.search(loc):
        return ["Europe"]
    return found


def analyse(rows: List[Dict[str, Any]], titles_only: bool = False) -> Dict[str, Dict[str, Any]]:
    """country -> {"jobs", "visa": Counter, "relocation": Counter, "residence": n, "companies": set, "offering": set}."""
    out: Dict[str, Dict[str, Any]] = collections.defaultdict(
        lambda: {"jobs": 0, "visa": collections.Counter(), "relocation": collections.Counter(), "residence": 0,
                 "companies": set(), "offering": set()})
    for r in rows:
        if titles_only and not title_included(r.get("title", "")):
            continue
        cs = countries(r.get("location", ""))
        if not cs:
            continue
        kind, _ = visa_wording(r.get("description", ""))
        reloc = relocation_wording(r.get("description", ""))
        res = residence_required(r.get("description", ""))
        for c in cs:
            o = out[c]
            o["jobs"] += 1
            o["visa"][kind] += 1
            o["relocation"][reloc] += 1
            o["residence"] += res
            o["companies"].add(r.get("company", ""))
            if kind == "offered":
                o["offering"].add(r.get("company", ""))
    return out


def _pct(n: int, d: int) -> str:
    return f"{n:>5} ({100 * n / d:4.1f}%)" if d else f"{n:>5}"


def report(stats: Dict[str, Dict[str, Any]], heading: str) -> None:
    print(f"\n{heading}")
    print(f"{'place':12} {'jobs':>6} {'offered':>14} {'refused':>14} {'unclear':>14} {'silent':>14} {'reloc. help':>14} "
          f"{'live-here':>14} {'cos':>5} {'cos offering':>12}")
    for c in [*COUNTRIES, "Europe"]:
        if c not in stats:
            continue
        o, n = stats[c], stats[c]["jobs"]
        v = o["visa"]
        print(f"{c:12} {n:>6} {_pct(v['offered'], n):>14} {_pct(v['refused'], n):>14} {_pct(v['mentioned'], n):>14} "
              f"{_pct(v['silent'], n):>14} {_pct(o['relocation']['offered'], n):>14} {_pct(o['residence'], n):>14} "
              f"{len(o['companies']):>5} {len(o['offering']):>12}")


def samples(rows: List[Dict[str, Any]], k: int, seed: int = 1) -> None:
    rnd = random.Random(seed)
    by_kind: Dict[str, List[tuple]] = collections.defaultdict(list)
    for r in rows:
        if countries(r.get("location", "")):
            kind, sent = visa_wording(r.get("description", ""))
            if kind != "silent":
                by_kind[kind].append((r["company"], r["title"], r["location"], sent))
    for kind in ("offered", "refused", "mentioned"):
        pick = rnd.sample(by_kind[kind], min(k, len(by_kind[kind])))
        print(f"\n--- {k} random '{kind}' of {len(by_kind[kind])} ---")
        for company, title, loc, sent in pick:
            print(f"* {company} | {title} | {loc}\n    {sent}")


def save(path: str, workers: int = 8) -> None:
    from job_hunt.scanner import _prefetch_jobs
    companies = [c for c in json.loads(Path("companies.json").read_text(encoding="utf-8")) if c.get("ats") in DESCRIBED_ATS]
    res = _prefetch_jobs(companies, workers)
    rows, failed = [], 0
    for c, (jobs, err, _) in zip(companies, res):
        failed += err is not None
        for j in jobs:
            keep = bool(countries(j.location))   # descriptions only where they are analysed: keeps the file small
            rows.append({"company": c["name"], "ats": c["ats"], "title": j.title, "location": j.location, "url": j.url,
                         "posted_at": j.posted_at, "is_remote": j.is_remote,
                         "description": j.description_text if keep else ""})
    Path(path).write_text(json.dumps(rows), encoding="utf-8")
    print(f"saved {len(rows)} jobs from {len(companies)} boards ({failed} failed) to {path}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", help="saved fetch (JSON list of rows with title/location/description)")
    ap.add_argument("--save", help="fetch the described ATS boards in companies.json and save the rows here")
    ap.add_argument("--sample", type=int, default=0, help="print N matched sentences per verdict, to read by hand")
    args = ap.parse_args(argv)
    if args.save:
        save(args.save)
        rows = json.loads(Path(args.save).read_text(encoding="utf-8"))
    elif args.jobs:
        rows = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    else:
        ap.error("give --jobs FILE or --save FILE")
    print(f"{len(rows)} jobs, {sum(bool(countries(r.get('location', ''))) for r in rows)} in a target place")
    report(analyse(rows), "All titles")
    report(analyse(rows, titles_only=True), "Titles with an include word (config.json candidate.titles, else the defaults)")
    if args.sample:
        samples(rows, args.sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

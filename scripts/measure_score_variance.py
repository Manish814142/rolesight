"""How much does a job's score change between runs of the same prompt? (T60)

    python scripts/measure_score_variance.py --label maybe --runs 5          # real Gemini: jobs x runs calls
    python scripts/measure_score_variance.py --label maybe --temperature 0   # try another temperature
    python scripts/measure_score_variance.py --from-runs runs.json           # re-analyse saved runs
    python scripts/measure_score_variance.py --ids g27,ab5 --model gemini-3.5-flash-lite   # named jobs, one model

Uses the labelled jobs in scripts/golden_set.csv and the current rubric. Prints, per job, the scores of
each run, and how many jobs had a spread over 20 points or crossed MIN_SCORE between runs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_golden_set import DEFAULT_GOLDEN_SET_PATH, load_golden_set  # noqa: E402

from job_hunt import llm_utils  # noqa: E402
from job_hunt.llm_utils import score_job_with_gemini  # noqa: E402
from job_hunt.main import load_config  # noqa: E402


def spread_report(runs: Dict[str, List[int]], thresholds: Sequence[int] = (60, 70), wide: int = 20) -> Dict[str, object]:
    """Summarise {job id: [score per run]}: wide spreads and jobs whose decision flips between runs."""
    spreads = {i: max(r) - min(r) for i, r in runs.items() if r}
    flips = {t: [i for i, r in runs.items() if len({s >= t for s in r}) > 1] for t in thresholds}
    return {
        "jobs": len(spreads),
        "wide": sorted(i for i, s in spreads.items() if s > wide),
        "mean_spread": sum(spreads.values()) / len(spreads) if spreads else 0.0,
        "flips": flips,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="maybe", help="score the jobs with this label (default maybe)")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--temperature", type=float, default=None, help="override gemini_temperature (default: the config's)")
    ap.add_argument("--from-runs", help="analyse a saved JSON {id: [scores]} instead of calling Gemini")
    ap.add_argument("--save", help="write the runs to this JSON file")
    ap.add_argument("--ids", help="comma-separated golden-set ids to score instead of --label/--limit")
    ap.add_argument("--model", help="score with this Gemini model only, no fallback (T70)")
    ap.add_argument("--csv", default=str(DEFAULT_GOLDEN_SET_PATH), help="labelled jobs CSV (default scripts/golden_set.csv; "
                    "scripts/golden_set_ai.csv for the AI / Forward Deployed set)")
    args = ap.parse_args(argv)
    if args.from_runs:
        runs = json.loads(Path(args.from_runs).read_text())
    else:
        config = load_config()
        if args.temperature is not None:
            config["gemini_temperature"] = args.temperature
        resume = Path(config["candidate"]["resume_path"]).read_text(encoding="utf-8")
        if args.ids:
            wanted = [i.strip() for i in args.ids.split(",") if i.strip()]
            jobs = [j for j in load_golden_set(args.csv) if j["id"] in wanted]
        else:
            jobs = [j for j in load_golden_set(args.csv) if j["label"] == args.label][: args.limit]
        original_models = llm_utils._gemini_models
        if args.model:  # no fallback: on 2026-10-06 ~9 of T60's 200 calls were silently answered by the other model
            llm_utils._gemini_models = lambda config: [args.model]  # type: ignore[assignment]
        runs = {}
        try:
            for j in jobs:
                payload = {"company": j["company"], "title": j["title"], "location": j["location"], "content": j["description"]}
                scores = []
                for _ in range(args.runs):
                    time.sleep(4.2)
                    scores.append(score_job_with_gemini(payload, resume, config, raise_on_error=True)["score"])
                runs[j["id"]] = scores
                print(f"{j['id']:5} {scores}", flush=True)
        finally:
            llm_utils._gemini_models = original_models  # type: ignore[assignment]
        if args.save:
            Path(args.save).write_text(json.dumps(runs, indent=1))
    rep = spread_report(runs)
    print(f"{rep['jobs']} jobs | spread over 20 points: {len(rep['wide'])} {rep['wide']} | mean spread {rep['mean_spread']:.1f}")  # type: ignore[arg-type]
    for t, ids in rep["flips"].items():  # type: ignore[attr-defined]
        print(f"decision at MIN_SCORE {t} changes between runs for {len(ids)} job(s): {ids}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

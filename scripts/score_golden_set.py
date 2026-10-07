"""Measure the Gemini scoring prompt against labelled jobs (T48).

    python scripts/score_golden_set.py                       # live: every job scored with the rubric
                                                             # off and with the current rubric
                                                             # (2 Gemini calls per job, ~14 min for 75 jobs)
    python scripts/score_golden_set.py --save-scores s.json  # also keep the scores
    python scripts/score_golden_set.py --from-scores s.json  # re-analyse saved scores, no API calls
    # compare models (T70): one prompt, one model each, no fallback (82 calls per run); then compare offline
    python scripts/score_golden_set.py --arms current --model gemini-3.1-flash-lite --save-scores a.json
    python scripts/score_golden_set.py --from-scores a.json b.json   # adds a job-by-job score agreement section

`scripts/golden_set.csv` holds real job postings (full descriptions as the scorer sees them),
a `label` (apply / maybe / no), who set it (`label_source`) and a one-line `label_reason`.
Rows marked `dev` informed the rubric's wording; rows marked `held-out` did not.

The labels are a judgement of fit against the candidate's resume and stated preferences. The
shipped ones come from a single rater (Claude, read from the job text) and are NOT confirmed by
Manish; the report says so until every row's `label_source` is `manish`.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt import llm_utils  # noqa: E402
from job_hunt.llm_utils import score_job_structured_with_gemini, score_job_with_gemini  # noqa: E402
from job_hunt.main import load_config  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("golden_set_scorer")

DEFAULT_GOLDEN_SET_PATH = Path("scripts/golden_set.csv")
LABELS = ("apply", "maybe", "no")
CONFIRMED_SOURCE = "manish"
# Arm value meaning "use structured scoring (T41)" instead of a rubric text.
STRUCTURED_ARM = "\0structured"
REQUIRED_COLUMNS = ("id", "split", "company", "title", "location", "url", "label", "label_source",
                    "label_reason", "description")


def load_golden_set(csv_path: Path | str = DEFAULT_GOLDEN_SET_PATH) -> List[Dict[str, str]]:
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Golden set CSV not found: {p}")
    with open(p, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{p} lacks columns: {sorted(missing)}")
        rows = [{k: (v or "").strip() if k != "description" else (v or "") for k, v in r.items()} for r in reader]
    for r in rows:
        r["label"] = r["label"].lower()
        if r["label"] not in LABELS:
            raise ValueError(f"job {r['id']}: label must be one of {LABELS}, got {r['label']!r}")
    return rows


def auc(scores: Sequence[float], positives: Sequence[bool]) -> float:
    """Chance that a random positive outscores a random negative (ties count half); nan if undefined."""
    pos = [s for s, y in zip(scores, positives) if y]
    neg = [s for s, y in zip(scores, positives) if not y]
    if not pos or not neg:
        return float("nan")
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def compute_metrics(scores: Sequence[int], labels: Sequence[str], min_score: int = 60) -> Dict[str, Any]:
    """Precision / recall at `min_score`, ranking quality (AUC) and ties among the top scores."""
    assert len(scores) == len(labels), "scores and labels must have equal length"
    passed = [i for i, s in enumerate(scores) if s >= min_score]
    apply_total = sum(lab == "apply" for lab in labels)
    fit_total = sum(lab != "no" for lab in labels)
    apply_found = sum(labels[i] == "apply" for i in passed)
    fit_found = sum(labels[i] != "no" for i in passed)
    false_pos = [i for i in passed if labels[i] == "no"]
    top = Counter(s for s in scores if s >= 85)
    tie_score, tie_count = top.most_common(1)[0] if top else (0, 0)
    return {
        "n": len(scores),
        "passes": len(passed),
        "apply_found": apply_found, "apply_total": apply_total,
        "fit_found": fit_found, "fit_total": fit_total,
        "false_positives": len(false_pos), "false_positive_indices": false_pos,
        "precision": fit_found / len(passed) if passed else float("nan"),
        "recall_apply": apply_found / apply_total if apply_total else float("nan"),
        "recall_fit": fit_found / fit_total if fit_total else float("nan"),
        "auc": auc(scores, [lab != "no" for lab in labels]),
        "top_count": sum(top.values()), "top_distinct": len(top),
        "max_tie_score": tie_score, "max_tie_count": tie_count,
    }


def paired_auc_diff_ci(a: Sequence[int], b: Sequence[int], labels: Sequence[str],
                       resamples: int = 2000, seed: int = 1) -> Tuple[float, float, float]:
    """Bootstrap (median, 2.5%, 97.5%) of AUC(b) - AUC(a) over the same jobs."""
    rng = random.Random(seed)
    n, diffs = len(labels), []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        pos = [labels[i] != "no" for i in idx]
        if len(set(pos)) < 2:
            continue
        diffs.append(auc([b[i] for i in idx], pos) - auc([a[i] for i in idx], pos))
    diffs.sort()
    if not diffs:
        return float("nan"), float("nan"), float("nan")
    return diffs[len(diffs) // 2], diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]


def banner(jobs: Sequence[Dict[str, str]]) -> List[str]:
    """Lines warning that the labels are not the candidate's own; empty once every row is his."""
    sources = Counter(j["label_source"] or "unknown" for j in jobs)
    unconfirmed = {s: n for s, n in sources.items() if s != CONFIRMED_SOURCE}
    if not unconfirmed:
        return []
    who = ", ".join(f"{n} by {s}" for s, n in sorted(unconfirmed.items()))
    return [
        "!! LABELS NOT CONFIRMED BY MANISH !!",
        f"   {who} (of {len(jobs)} rows). A single rater's reading of the job text is a rough estimate,",
        "   not ground truth. To confirm a row, correct its `label` if needed and set `label_source` to `manish`.",
    ]


def score_arms(jobs: Sequence[Dict[str, str]], resume: str, config: Dict[str, Any],
               arms: Dict[str, str], sleep_interval: float = 4.2,
               model: Optional[str] = None) -> Dict[str, Dict[str, Optional[int]]]:
    """Score every job once per arm (arm name -> rubric text) with real Gemini calls.

    A failed call gives None (never 0), so a quota error cannot masquerade as a low score. With `model`, every
    call goes to that model only: no fallback, so a model comparison never mixes in the other model (T70).
    """
    original = llm_utils.SCORING_RUBRIC
    original_models = llm_utils._gemini_models
    if model:
        llm_utils._gemini_models = lambda config: [model]  # type: ignore[assignment]
    out: Dict[str, Dict[str, Optional[int]]] = {name: {} for name in arms}
    try:
        for n, j in enumerate(jobs, 1):
            payload = {"company": j["company"], "title": j["title"], "location": j["location"],
                       "content": j["description"]}
            for name, rubric in arms.items():
                time.sleep(sleep_interval)
                try:
                    if rubric == STRUCTURED_ARM:
                        out[name][j["id"]] = score_job_structured_with_gemini(payload, resume, config)["score"]
                    else:
                        llm_utils.SCORING_RUBRIC = rubric
                        out[name][j["id"]] = score_job_with_gemini(payload, resume, config, raise_on_error=True)["score"]
                except Exception as e:  # noqa: BLE001
                    logger.error("job %s arm %s failed: %s", j["id"], name, e)
                    out[name][j["id"]] = None
            logger.info("[%d/%d] %s %s", n, len(jobs), j["id"], {a: out[a][j["id"]] for a in arms})
    finally:
        llm_utils.SCORING_RUBRIC = original
        llm_utils._gemini_models = original_models  # type: ignore[assignment]
    return out


def score_agreement(a: Dict[str, Optional[int]], b: Dict[str, Optional[int]],
                    min_scores: Sequence[int] = (60, 70)) -> Dict[str, Any]:
    """How far two arms' scores are apart on the jobs both scored (a failed call is left out, never 0)."""
    ids = [i for i in a if a[i] is not None and b.get(i) is not None]
    diffs = [abs(int(a[i]) - int(b[i])) for i in ids]  # type: ignore[arg-type]
    return {
        "jobs": len(ids),
        "mean_abs_diff": sum(diffs) / len(diffs) if diffs else float("nan"),
        "within_10": sum(d <= 10 for d in diffs),
        "decision_changes": {t: [i for i in ids if (a[i] >= t) != (b[i] >= t)] for t in min_scores},  # type: ignore[operator]
    }


def _fmt(x: float, pct: bool = False) -> str:
    if x != x:  # nan
        return "  n/a"
    return f"{x:4.0%}" if pct else f"{x:5.3f}"


def print_report(jobs: Sequence[Dict[str, str]], scores: Dict[str, Dict[str, Optional[int]]],
                 min_scores: Sequence[int] = (60, 70)) -> None:
    arms = list(scores)
    w = max([10] + [len(a) for a in arms])
    print("=" * 88)
    print(" SCORING PROMPT vs LABELLED JOBS")
    print("=" * 88)
    for line in banner(jobs):
        print(line)
    groups = [("all", list(jobs))] + [(s, [j for j in jobs if j["split"] == s])
                                      for s in sorted({j["split"] for j in jobs})]
    for name, group in groups:
        usable = [j for j in group if all(scores[a].get(j["id"]) is not None for a in arms)]
        if not usable:
            continue
        labels = [j["label"] for j in usable]
        dropped = len(group) - len(usable)
        c = Counter(labels)
        print(f"\n--- {name}: {len(usable)} jobs ({c['apply']} apply, {c['maybe']} maybe, {c['no']} no)"
              + (f"; {dropped} skipped because a Gemini call failed" if dropped else ""))
        by_arm = {a: [int(scores[a][j["id"]] or 0) for j in usable] for a in arms}
        for t in min_scores:
            print(f"  MIN_SCORE {t}:   passes  apply found  false positives  precision  recall(apply)  recall(apply+maybe)")
            for a in arms:
                m = compute_metrics(by_arm[a], labels, t)
                print(f"    {a:{w}} {m['passes']:7}  {m['apply_found']:3}/{m['apply_total']:<3}  "
                      f"{m['false_positives']:13}  {_fmt(m['precision'], True):>9}  {_fmt(m['recall_apply'], True):>13}"
                      f"  {_fmt(m['recall_fit'], True):>19}")
        print("  ranking (AUC, apply+maybe vs no) and ties among scores >= 85:")
        for a in arms:
            m = compute_metrics(by_arm[a], labels, min_scores[0])
            print(f"    {a:{w}} AUC {_fmt(m['auc'])}   top scores: {m['top_count']} jobs, {m['top_distinct']} distinct values,"
                  f" biggest tie {m['max_tie_count']} at {m['max_tie_score']}")
        for other in arms[1:] if len(usable) >= 20 else []:
            med, lo, hi = paired_auc_diff_ci(by_arm[arms[0]], by_arm[other], labels)
            print(f"  AUC({other}) - AUC({arms[0]}): median {med:+.3f}, 95% bootstrap CI [{lo:+.3f}, {hi:+.3f}]"
                  + ("  (CI includes 0: no ranking difference shown)" if lo <= 0 <= hi else ""))
        if name == "all" and len(arms) > 1:
            print("  score agreement (same jobs; a pair of runs of ONE model shows its run-to-run noise):")
            for i, a in enumerate(arms):
                for b in arms[i + 1:]:
                    ag = score_agreement({j["id"]: scores[a][j["id"]] for j in usable},
                                         {j["id"]: scores[b][j["id"]] for j in usable}, min_scores)
                    flips = ", ".join(f"{len(v)} at {t}" for t, v in ag["decision_changes"].items())
                    print(f"    {a} vs {b}: {ag['jobs']} jobs, mean |difference| {ag['mean_abs_diff']:.1f}, "
                          f"within 10 points {ag['within_10']}/{ag['jobs']}, pass/fail decision differs: {flips}")
    print("\n" + "=" * 88)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_GOLDEN_SET_PATH), help="labelled jobs CSV")
    ap.add_argument("--min-score", type=int, nargs="+", default=[60, 70], help="thresholds to report")
    ap.add_argument("--save-scores", help="write the scores to this JSON file")
    ap.add_argument("--from-scores", nargs="+", help="analyse scores saved earlier (one or more files) instead of calling Gemini")
    ap.add_argument("--arms", nargs="+", choices=["off", "current", "structured"], default=["off", "current"],
                    help="which prompts to score (default: off current)")
    ap.add_argument("--model", help="score with this Gemini model only, no fallback; arms are saved as ARM@MODEL (T70)")
    ap.add_argument("--limit", type=int, help="only the first N jobs (live runs)")
    ap.add_argument("--structured", action="store_true", help="also score with structured scoring (T41)")
    args = ap.parse_args(argv)

    jobs = load_golden_set(args.csv)
    if args.from_scores:
        scores = {}
        for f in args.from_scores:
            for arm, values in json.loads(Path(f).read_text(encoding="utf-8")).items():
                if arm in scores:
                    sys.exit(f"arm {arm!r} appears twice in --from-scores; rename it in one file")
                scores[arm] = values
    else:
        if args.limit:
            jobs = jobs[: args.limit]
        config = load_config()
        resume_path = Path(config.get("candidate", {}).get("resume_path", ""))
        if not resume_path.is_file():
            logger.error("Resume not found at %s", resume_path)
            return 1
        texts = {"off": "", "current": llm_utils.SCORING_RUBRIC, "structured": STRUCTURED_ARM}
        names = list(args.arms) + (["structured"] if args.structured and "structured" not in args.arms else [])
        arms = {(f"{n}@{args.model}" if args.model else n): texts[n] for n in names}
        scores = score_arms(jobs, resume_path.read_text(encoding="utf-8"), config, arms, model=args.model)
        if args.save_scores:
            Path(args.save_scores).write_text(json.dumps(scores, indent=1), encoding="utf-8")
    print_report(jobs, scores, args.min_score)
    return 0


if __name__ == "__main__":
    sys.exit(main())

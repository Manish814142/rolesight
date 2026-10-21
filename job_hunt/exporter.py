"""Incremental CSV exporter for scan results."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

from job_hunt import visa
from job_hunt.llm_utils import GEMINI_DEFAULT_MODEL, current_rubric_ids
from job_hunt.places import active_places

# Where the files go (T130): the two the person opens every day keep fixed names at the top of output/ (scanner.OPEN_MATCHES_FILE and
# LAST_SCAN_FILE), every dated per-scan file goes to output/history/, drafts to output/drafts/ (drafter.DRAFTS_DIR).
OUTPUT_DIR = Path("output")
HISTORY_DIR = OUTPUT_DIR / "history"

# In reading order (T128): the score first, the file is sorted by it; the long link columns after the text; Worth Applying, which only
# repeats the score against min_score, with the date at the end. Optional columns (OPTIONAL_COLUMNS, Model, Rubric) follow.
EXPORT_FIELDS: List[str] = [
    "Score (%)",
    "Company",
    "ATS",                  # the platform the job is posted on, as companies.json spells it: a filter column (T122)
    "Role",
    "Location",
    "Posted",
    "Reason",
    "Application URL",
    "LinkedIn people",
    "Worth Applying",
    "Scan Date",
]


def linkedin_people_search_url(company: str) -> str:
    """LinkedIn people search for engineers at `company`: a way to find someone for a referral. "" without a name."""
    name = (company or "").strip()
    if not name:
        return ""
    return "https://www.linkedin.com/search/results/people/?keywords=" + quote(f"{name} software engineer", safe="")


def _posted_display(posted_at: str) -> str:
    """ISO timestamps -> YYYY-MM-DD; relative text (Workday "Posted 5 Days Ago") as-is."""
    s = (posted_at or "").strip()
    return s[:10] if len(s) >= 10 and s[4] == "-" and s[7] == "-" else s


# Written only when some job has a value, so no column is always empty (T36): Stack comes from the deprecated
# non-Gemini scorer, the fit/years/cap columns from structured scoring (scoring_mode: structured, T41).
OPTIONAL_COLUMNS = {
    "Visa": "visa",                    # a job outside the home country (T138): the posting's words, then the company record
    "Stack": "stack",
    "Stack fit": "stack_fit",
    "Role fit": "role_fit",
    "Seniority fit": "seniority_fit",
    "Location fit": "location_fit",
    "Min years": "min_years",
    "Capped by": "capped_by",
    "Application": "application",      # `autopilot mark` (T38), filled by `autopilot export`
}


def _model_column_needed(jobs: List[Dict[str, Any]]) -> bool:
    """The "Model" column (T71) is written when the jobs mix models or any was scored by a model other than the
    default primary (T70: another calibration). A normal scan, all on the primary, keeps today's columns; unknown
    models (rows written before T71, deprecated providers) never add the column."""
    models = {j.get("model") for j in jobs if j.get("model")}
    return len(models) > 1 or bool(models - {GEMINI_DEFAULT_MODEL})


def _rubric_column_needed(jobs: List[Dict[str, Any]]) -> bool:
    """The "Rubric" column (T97) is written when some score is not from the prompt this checkout sends: an older
    rubric, or none recorded (a row scored before T97, or by a deprecated provider), provided at least one score does
    carry an id: until then every row is "unknown" and the column would be empty (T36). Unlike the model, an unknown
    rubric counts, because those rows are exactly the ones that may predate a rubric change."""
    rubrics = [j.get("rubric") for j in jobs]
    return any(rubrics) and any(r not in current_rubric_ids() for r in rubrics)


def job_to_export_row(j: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an internal job dictionary to a canonical export CSV row."""
    worth = j.get("worth_applying")
    return {
        "Company": j.get("company", ""),
        "ATS": j.get("ats") or "",
        "Role": j.get("extracted_title") or j.get("title", ""),
        "Location": j.get("location_remote") or j.get("location", ""),
        "Posted": _posted_display(j.get("posted_at", "")),
        "Application URL": j.get("url", ""),
        "LinkedIn people": linkedin_people_search_url(j.get("company", "")),
        "Score (%)": j.get("score", ""),
        "Reason": j.get("reason", ""),
        "Worth Applying": "Yes" if worth else ("No" if worth is False else ""),
        "Scan Date": j.get("scan_date", ""),
        **{col: ("" if j.get(key) is None else j.get(key)) for col, key in OPTIONAL_COLUMNS.items()},
        "Model": j.get("model") or "",
        "Rubric": j.get("rubric") or "",
    }


def job_from_db_row(r: Dict[str, Any], threshold: Optional[int]) -> Dict[str, Any]:
    """A `jobs` row of data/jobs.db as an export job dict (T32, T39). "Worth Applying" compares with `threshold`
    (None: unknown, left blank)."""
    app = r.get("application_status")
    return {
        "company": r.get("company") or "", "ats": r.get("ats") or "", "title": r.get("title") or "", "location": r.get("location") or "",
        "url": r.get("url") or "", "score": r.get("score"), "reason": r.get("score_reason") or "",
        "posted_at": r.get("posted_at") or "", "scan_date": (r.get("scored_at") or "")[:10],
        "worth_applying": None if threshold is None else int(r["score"]) >= threshold,
        "model": r.get("score_model"),
        "rubric": r.get("score_rubric"),
        "application": f"{app} {r.get('application_date') or ''}".strip() if app else "",  # `autopilot mark` (T38)
        "visa": visa.note(r.get("company") or "", r.get("location") or "", r.get("description") or "", active_places()),
    }


def get_incremental_csv_path(
    base_name: str,
    out_dir: Union[Path, str] = HISTORY_DIR,
) -> Path:
    """
    Generate an incremental CSV path.
    If 'base_name.csv' exists, increments to 'base_name_1.csv', 'base_name_2.csv', etc.
    """
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f"{base_name}.csv"
    counter = 1
    while out_path.exists():
        out_path = directory / f"{base_name}_{counter}.csv"
        counter += 1
    return out_path


def export_jobs_to_csv(
    jobs: List[Dict[str, Any]],
    base_name: Optional[str] = None,
    out_dir: Union[Path, str] = HISTORY_DIR,
    out_path: Optional[Path] = None,
) -> Path:
    """
    Export jobs to CSV with non-overwriting incremental naming if out_path not specified.
    """
    if out_path is None:
        if base_name is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            base_name = f"jobs_{date_str}"
        out_path = get_incremental_csv_path(base_name=base_name, out_dir=out_dir)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    extra = [col for col, key in OPTIONAL_COLUMNS.items() if any(j.get(key) not in (None, "") for j in jobs)]
    if _model_column_needed(jobs):
        extra.append("Model")
    if _rubric_column_needed(jobs):
        extra.append("Rubric")
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPORT_FIELDS + extra, extrasaction="ignore")
        writer.writeheader()
        for j in jobs:
            writer.writerow(job_to_export_row(j))

    return out_path

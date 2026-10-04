"""Incremental CSV exporter for scan results."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

EXPORT_FIELDS: List[str] = [
    "Company",
    "Role",
    "Location",
    "Posted",
    "Application URL",
    "Score (%)",
    "Stack",
    "Region",
    "Reason",
    "Worth Applying",
    "Scan Date",
]


def _posted_display(posted_at: str) -> str:
    """ISO timestamps -> YYYY-MM-DD; relative text (Workday "Posted 5 Days Ago") as-is."""
    s = (posted_at or "").strip()
    return s[:10] if len(s) >= 10 and s[4] == "-" and s[7] == "-" else s


def job_to_export_row(j: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an internal job dictionary to a canonical export CSV row."""
    worth = j.get("worth_applying")
    return {
        "Company": j.get("company", ""),
        "Role": j.get("extracted_title") or j.get("title", ""),
        "Location": j.get("location_remote") or j.get("location", ""),
        "Posted": _posted_display(j.get("posted_at", "")),
        "Application URL": j.get("url", ""),
        "Score (%)": j.get("score", ""),
        "Stack": j.get("stack", ""),
        "Region": j.get("region", ""),
        "Reason": j.get("reason", ""),
        "Worth Applying": "Yes" if worth else ("No" if worth is False else ""),
        "Scan Date": j.get("scan_date", ""),
    }


def get_incremental_csv_path(
    base_name: str,
    out_dir: Union[Path, str] = "output",
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
    out_dir: Union[Path, str] = "output",
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

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for j in jobs:
            writer.writerow(job_to_export_row(j))

    return out_path

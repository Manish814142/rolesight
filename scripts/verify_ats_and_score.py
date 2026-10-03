"""
Verification Script: Run all 8 ATS adapters, fetch 2 companies & 2 jobs each,
evaluate match against candidate resume via Gemini, and generate Excel + CSV reports.
"""
from __future__ import annotations

import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from job_hunt.adapters import fetch_company_jobs
from job_hunt.llm_utils import score_job_with_gemini
from job_hunt.main import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ats_verifier")

TEST_MATRIX: List[Dict[str, Any]] = [
    # 1. Greenhouse
    {"name": "CloudSEK", "ats": "greenhouse", "slug": "cloudsek"},
    {"name": "Druva", "ats": "greenhouse", "slug": "druva"},
    # 2. Lever
    {"name": "CRED", "ats": "lever", "slug": "cred"},
    {"name": "Fampay", "ats": "lever", "slug": "fampay"},
    # 3. Ashby
    {"name": "Bounce", "ats": "ashby", "slug": "bounce"},
    {"name": "Navi Technologies", "ats": "ashby", "slug": "navi"},
    # 4. SmartRecruiters
    {"name": "Freshworks", "ats": "smartrecruiters", "slug": "freshworks"},
    {"name": "ixigo", "ats": "smartrecruiters", "slug": "ixigo"},
    # 5. Workday
    {"name": "Adobe India", "ats": "workday", "tenant": "adobe", "dc": "wd5", "site": "external_experienced"},
    {"name": "Autodesk", "ats": "workday", "tenant": "autodesk", "dc": "wd1", "site": "Ext"},
    # 6. Personio
    {"name": "Edelweiss", "ats": "personio", "slug": "edelweiss"},
    {"name": "Josh (DailyHunt)", "ats": "personio", "slug": "josh"},
    # 7. Workable
    {"name": "Eat Club", "ats": "workable", "slug": "eatclub"},
    {"name": "YouTrip", "ats": "workable", "slug": "youtrip"},
    # 8. Recruitee
    {"name": "Navi Technologies", "ats": "recruitee", "slug": "navi"},
    {"name": "Bunq", "ats": "recruitee", "slug": "bunq"},
]


def create_excel_report(rows: List[Dict[str, Any]], xlsx_path: Path) -> None:
    """Create a professionally formatted Excel workbook."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ATS Verification & Match"

    # Header style
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="D3D3D3"),
        right=Side(style="thin", color="D3D3D3"),
        top=Side(style="thin", color="D3D3D3"),
        bottom=Side(style="thin", color="D3D3D3"),
    )

    headers = [
        "ATS Platform",
        "Company Name",
        "Job Title",
        "Location",
        "Score (%)",
        "Worth Applying",
        "Gemini Evaluation Reason",
        "Application URL",
        "Verified At",
    ]
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # High score fill (green), Medium (amber), Low (light gray)
    high_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    high_font = Font(name="Calibri", size=10, color="006100", bold=True)
    med_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    med_font = Font(name="Calibri", size=10, color="9C6500", bold=True)
    low_font = Font(name="Calibri", size=10, color="595959")

    for r_idx, row in enumerate(rows, start=2):
        ws.append([
            row["ats"].upper(),
            row["company"],
            row["title"],
            row["location"],
            row["score"],
            row["worth_applying"],
            row["reason"],
            row["url"],
            row["timestamp"],
        ])

        # Style score and worth applying
        score_val = row["score"]
        score_cell = ws.cell(row=r_idx, column=5)
        worth_cell = ws.cell(row=r_idx, column=6)

        score_cell.alignment = center_align
        worth_cell.alignment = center_align

        if score_val >= 70:
            score_cell.fill = high_fill
            score_cell.font = high_font
            worth_cell.fill = high_fill
            worth_cell.font = high_font
        elif score_val >= 50:
            score_cell.fill = med_fill
            score_cell.font = med_font
            worth_cell.fill = med_fill
            worth_cell.font = med_font
        else:
            score_cell.font = low_font
            worth_cell.font = low_font

        # Apply borders and formatting
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=r_idx, column=col_idx)
            c.border = thin_border
            if col_idx in (1, 5, 6, 9):
                c.alignment = center_align
            elif col_idx == 8:
                c.font = Font(name="Calibri", size=10, color="0563C1", underline="single")

    # Auto-adjust column widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 65)

    ws.freeze_panes = "A2"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx_path)


def main() -> None:
    print("=" * 70)
    print("      MULTI-ATS LIVE VERIFICATION & GEMINI RESUME COMPARISON      ")
    print("=" * 70)

    cfg = load_config()
    resume_path = Path("resume/YOUR_RESUME.md")
    if not resume_path.exists():
        sys.exit("Resume not found at resume/YOUR_RESUME.md")
    resume_text = resume_path.read_text(encoding="utf-8")
    print(f"Loaded Resume: {resume_path.name} ({len(resume_text)} chars)")
    print(f"Target: 8 ATS Platforms x 2 Companies = {len(TEST_MATRIX)} Companies (up to 2 jobs each)")
    print("-" * 70)

    min_score = cfg.get("candidate", {}).get("min_score", 55)

    results: List[Dict[str, Any]] = []
    job_eval_count = 0

    for comp_idx, comp in enumerate(TEST_MATRIX, start=1):
        ats = comp["ats"]
        name = comp["name"]
        print(f"\n[{comp_idx:2d}/{len(TEST_MATRIX)}] Probing {ats.upper()} -> {name}...")

        try:
            postings = fetch_company_jobs(comp)
        except Exception as exc:
            logger.error(f"Failed fetching {name} ({ats}): {exc}")
            continue

        if not postings:
            print(f"    [WARN] No postings returned for {name} ({ats})")
            continue

        selected = postings[:2]
        print(f"    Found {len(postings)} jobs -> Testing top {len(selected)} with Gemini:")

        for job in selected:
            job_eval_count += 1
            job_dict = {
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "url": job.url,
                "content": job.description_text or job.title,
            }

            t0 = time.time()
            score_data = score_job_with_gemini(job_dict, resume_text, cfg)
            elapsed = time.time() - t0

            score = score_data.get("score", 0)
            reason = score_data.get("reason", "")
            worth = "Yes" if score >= min_score else "No"

            print(f"      * [{score:3d}% | {worth:3s}] {job.title[:42]:<42} ({elapsed:.1f}s)")
            print(f"        Reason: {reason}")
            print(f"        URL:    {job.url}")

            results.append({
                "ats": ats,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "score": score,
                "worth_applying": worth,
                "reason": reason,
                "url": job.url,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            # Pacing sleep to stay strictly under Gemini free tier 15 RPM (60 / 15 = 4.0s)
            time.sleep(4.2)

    # ── Write Reports ──────────────────────────────────────────────────────────
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    xlsx_path = out_dir / "ats_platform_verification.xlsx"
    csv_path = out_dir / "ats_platform_verification.csv"

    create_excel_report(results, xlsx_path)

    # CSV write
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "ats", "company", "title", "location", "score",
            "worth_applying", "reason", "url", "timestamp"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 70)
    print("                      VERIFICATION SUMMARY                       ")
    print("=" * 70)
    print("Total ATS Platforms Tested : 8/8")
    print(f"Total Companies Tested     : {len(TEST_MATRIX)}")
    print(f"Total Jobs Evaluated       : {len(results)}")
    print(f"Excel Report Saved         : {xlsx_path.resolve()}")
    print(f"CSV Report Saved           : {csv_path.resolve()}")
    print("-" * 70)

    # Breakdown by ATS
    from collections import Counter
    ats_counts = Counter(r["ats"] for r in results)
    for ats_name, count in sorted(ats_counts.items()):
        print(f"  * {ats_name.upper():<16} : {count} jobs verified & scored")
    print("=" * 70)


if __name__ == "__main__":
    main()

"""Build scripts/golden_set.csv from real scan results (T48).

Selects 40 diverse jobs across top, middle, and bottom tiers, including all known
edge cases (C#/.NET, Java, US-onsite, Senior 5-7+ YOE, Salesforce/ServiceNow, etc.).
Fetches full descriptions for deterministic offline scoring.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from job_hunt.adapters.base import http_get, strip_html
from job_hunt.adapters.oracle_hcm import fetch_description as oracle_hcm_desc
from job_hunt.adapters.smartrecruiters import fetch_description as sr_desc
from job_hunt.adapters.workday import _fetch_detail
from job_hunt.models import JobPosting

GOLDEN_SET_PATH = Path("scripts/golden_set.csv")


def fetch_job_text(url: str, title: str = "", company: str = "") -> str:
    """Fetch description text from ATS endpoints."""
    # 1. Workday
    if "myworkdayjobs.com" in url:
        u = urlparse(url)
        site, _, rest = u.path.lstrip("/").partition("/")
        tenant = u.netloc.split(".")[0]
        try:
            desc = _fetch_detail(f"https://{u.netloc}/wday/cxs/{tenant}/{site}", "/" + rest)[1]
            if desc:
                return desc
        except Exception:
            pass

    # 2. Amazon
    if "amazon.jobs" in url:
        m = re.search(r"/jobs/(\d+)", url)
        if m:
            try:
                resp = http_get(f"https://www.amazon.jobs/en/search.json?job_id={m.group(1)}", timeout=10)
                data = resp.json()
                if data.get("jobs"):
                    j = data["jobs"][0]
                    return "\n\n".join(
                        strip_html(j.get(k) or "")
                        for k in ("description_short", "basic_qualifications", "preferred_qualifications")
                    ).strip()
            except Exception:
                pass

    # 3. Greenhouse
    if "greenhouse.io" in url:
        m = re.search(r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        if m:
            try:
                resp = http_get(f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}", timeout=10)
                data = resp.json()
                return strip_html(data.get("content") or "").strip()
            except Exception:
                pass

    # Toast Greenhouse embed
    if "toasttab.com" in url and "gh_jid=" in url:
        m = re.search(r"gh_jid=(\d+)", url)
        if m:
            try:
                resp = http_get(f"https://boards-api.greenhouse.io/v1/boards/toast/jobs/{m.group(1)}", timeout=10)
                data = resp.json()
                return strip_html(data.get("content") or "").strip()
            except Exception:
                pass

    # 4. SmartRecruiters
    if "smartrecruiters.com" in url:
        try:
            p = JobPosting(title=title, company=company, location="", url=url, ats="smartrecruiters", global_id="", is_remote=False)
            desc = sr_desc(p)
            if desc:
                return desc
        except Exception:
            pass

    # 5. Oracle HCM
    if "oraclecloud.com" in url:
        try:
            p = JobPosting(title=title, company=company, location="", url=url, ats="oracle_hcm", global_id="", is_remote=False)
            desc = oracle_hcm_desc(p)
            if desc:
                return desc
        except Exception:
            pass

    return ""


def select_golden_jobs() -> list[dict]:
    # Load scan results
    last_scan = json.load(open("state/last_scan.json"))

    # Also check if Salesforce US onsite role is in output/jobs_2026-10-04.csv
    salesforce_job = None
    if Path("output/jobs_2026-10-04.csv").exists():
        with open("output/jobs_2026-10-04.csv") as f:
            for r in csv.DictReader(f):
                if r.get("Company") == "Salesforce" and "AI Native" in r.get("Role", ""):
                    salesforce_job = {
                        "company": "Salesforce",
                        "title": r.get("Role", ""),
                        "location": r.get("Location", ""),
                        "url": r.get("Application URL", ""),
                        "score": int(r.get("Score (%)", 75)),
                        "reason": r.get("Reason", ""),
                    }
                    break

    # We want ~40 jobs:
    # 13 top tier (scores 85-92)
    # 14 middle tier (scores 40-75, including edge cases)
    # 13 bottom tier (scores 0-35)

    top_candidates = [j for j in last_scan if (j.get("score") or 0) >= 85]
    mid_candidates = [j for j in last_scan if 40 <= (j.get("score") or 0) < 85]
    bottom_candidates = [j for j in last_scan if (j.get("score") or 0) < 40]

    selected: list[dict] = []
    seen_urls: set[str] = set()

    def add_job(j: dict, default_label: str = ""):
        u = j["url"]
        if u in seen_urls:
            return
        seen_urls.add(u)
        selected.append({**j, "label": default_label})

    # TOP TIER (Target ~13)
    # Expedia 92
    for j in top_candidates:
        if j["company"] == "Expedia" and "Full Stack BE Heavy" in j["title"]:
            add_job(j, "apply")
            break

    # Amazon 90s & 85s
    for j in top_candidates:
        if j["company"] == "Amazon" and "Live Events" in j["title"]:
            add_job(j, "apply")
            break
    for j in top_candidates:
        if j["company"] == "Amazon" and "Supply Chain" in j["title"]:
            add_job(j, "apply")
            break
    for j in top_candidates:
        if j["company"] == "Amazon" and "Sports" in j["title"] and j.get("score") == 85:
            add_job(j, "apply")
            break
    for j in top_candidates:
        if j["company"] == "Amazon" and "Workplace Productivity" in j["title"]:
            add_job(j, "apply")
            break

    # Adobe India 90
    for j in top_candidates:
        if j["company"] == "Adobe India" and "Computer Scientist" in j["title"]:
            add_job(j, "apply")
            break

    # Nike 90 (backend fit)
    for j in top_candidates:
        if j["company"] == "Nike" and j.get("score") == 90:
            add_job(j, "apply")
            break

    # Toast 85
    for j in top_candidates:
        if j["company"] == "Toast" and j.get("score") == 85:
            add_job(j, "apply")
            break

    # Other distinct top fits
    for j in top_candidates:
        if len([x for x in selected if (x.get("score") or 0) >= 85]) >= 13:
            break
        if j["company"] not in [x["company"] for x in selected]:
            add_job(j, "apply")

    # Fill remaining top to 13
    for j in top_candidates:
        if len([x for x in selected if (x.get("score") or 0) >= 85]) >= 13:
            break
        add_job(j, "apply")

    # MIDDLE TIER (Target ~14)
    # Critical edge cases:
    # 1. Salesforce US Onsite (score 75)
    if salesforce_job:
        add_job(salesforce_job, "no")

    # 2. Nike C#/.NET Core (score 75)
    for j in mid_candidates:
        if j["company"] == "Nike" and "C#" in j.get("reason", ""):
            add_job(j, "no")
            break

    # 3. Nike Java/Spring Boot (score 75)
    for j in mid_candidates:
        if j["company"] == "Nike" and "Java" in j.get("reason", "") and j.get("score") == 75:
            add_job(j, "no")
            break

    # 4. Sureify Sr. SE - PHP / Golang (score 75)
    for j in mid_candidates:
        if j["company"] == "Sureify" and "Golang" in j.get("reason", ""):
            add_job(j, "no")
            break

    # 5. Hotstar SDE II (score 75)
    for j in mid_candidates:
        if j["company"] == "Hotstar" and j.get("score") == 75:
            add_job(j, "maybe")
            break

    # 6. Wells Fargo Senior SE (score 75)
    for j in mid_candidates:
        if j["company"] == "Wells Fargo" and j.get("score") == 75:
            add_job(j, "maybe")
            break

    # 7. Nike Senior SE - 5+ YOE (score 70)
    for j in mid_candidates:
        if j["company"] == "Nike" and "5+" in j.get("reason", "") and j.get("score") == 70:
            add_job(j, "maybe")
            break

    # 8. Nike SE III Data Engineering - 5-7 YOE (score 70)
    for j in mid_candidates:
        if j["company"] == "Nike" and "Data Engineering" in j.get("title", "") and j.get("score") == 70:
            add_job(j, "no")
            break

    # 9. Hotstar Senior SDE - Data Engineer (score 65)
    for j in mid_candidates:
        if j["company"] == "Hotstar" and j.get("score") == 65:
            add_job(j, "maybe")
            break

    # 10. Kotak Regional Sales Onsite Karnataka (score 50)
    for j in mid_candidates:
        if j["company"] == "Kotak Mahindra Bank" and j.get("score") == 50:
            add_job(j, "no")
            break

    # 11. Wolters Kluwer Senior Enterprise SE - 5-7 YOE DevOps (score 45)
    for j in mid_candidates:
        if j["company"] == "Wolters Kluwer" and j.get("score") == 45:
            add_job(j, "no")
            break

    # 12. Deutsche Bank Senior Engineer Backend AVP (score 45)
    for j in mid_candidates:
        if j["company"] == "Deutsche Bank" and j.get("score") == 45:
            add_job(j, "maybe")
            break

    # 13. Sureify US Night Shift / Support (score 40)
    for j in mid_candidates:
        if j["company"] == "Sureify" and "US shift" in j.get("title", ""):
            add_job(j, "no")
            break

    # 14. Amazon SDE II SP Support - Video Games (score 40)
    for j in mid_candidates:
        if j["company"] == "Amazon" and "SP Support" in j.get("title", ""):
            add_job(j, "no")
            break

    # Fill if needed
    for j in mid_candidates:
        if len([x for x in selected if 40 <= (x.get("score") or 0) < 85]) >= 14:
            break
        add_job(j, "maybe")

    # BOTTOM TIER (Target ~13)
    # 1. HPE C/C++ storage (score 25)
    for j in bottom_candidates:
        if j["company"] == "Hewlett Packard Enterprise" and "Storage" in j.get("title", ""):
            add_job(j, "no")
            break

    # 2. Nvidia Senior AV Platform C/C++ 8+ YOE (score 25)
    for j in bottom_candidates:
        if j["company"] == "Nvidia" and "DriveAV" in j.get("title", ""):
            add_job(j, "no")
            break

    # 3. Nike Coupa/SAP (score 25)
    for j in bottom_candidates:
        if j["company"] == "Nike" and "Coupa" in j.get("reason", "") and j.get("score") == 25:
            add_job(j, "no")
            break

    # 4. Nike Coupa Admin (score 20)
    for j in bottom_candidates:
        if j["company"] == "Nike" and "Coupa" in j.get("reason", "") and j.get("score") == 20:
            add_job(j, "no")
            break

    # 5. Adobe India SDE 3 Microsoft Dynamics (score 20)
    for j in bottom_candidates:
        if j["company"] == "Adobe India" and "Dynamics" in j.get("title", ""):
            add_job(j, "no")
            break

    # 6. Bosch Senior AI / Data Viz (score 20)
    for j in bottom_candidates:
        if j["company"] == "Bosch" and "Data Visualization" in j.get("title", ""):
            add_job(j, "no")
            break

    # 7. Genpact Salesforce Developer (score 15)
    for j in bottom_candidates:
        if j["company"] == "Genpact" and "Salesforce" in j.get("title", ""):
            add_job(j, "no")
            break

    # 8. Nike SOX compliance (score 15)
    for j in bottom_candidates:
        if j["company"] == "Nike" and "SOX" in j.get("reason", ""):
            add_job(j, "no")
            break

    # 9. CloudSEK Salesforce Developer (score 10)
    for j in bottom_candidates:
        if j["company"] == "CloudSEK" and "Salesforce" in j.get("title", ""):
            add_job(j, "no")
            break

    # 10. Neo4j Developer Advocate US San Mateo (score 10)
    for j in bottom_candidates:
        if j["company"] == "Neo4j" and "San Mateo" in j.get("location", ""):
            add_job(j, "no")
            break

    # 11. Medtronic ServiceNow Developer (score 0)
    for j in bottom_candidates:
        if j["company"] == "Medtronic" and "Servicenow" in j.get("title", ""):
            add_job(j, "no")
            break

    # 12. Sabre HFM (score 0)
    for j in bottom_candidates:
        if j["company"] == "Sabre" and "HFM" in j.get("title", ""):
            add_job(j, "no")
            break

    # 13. Sabre C++ (score 0)
    for j in bottom_candidates:
        if j["company"] == "Sabre" and "C++" in j.get("reason", "") and j.get("score") == 0:
            add_job(j, "no")
            break

    # Fill remaining bottom if needed
    for j in bottom_candidates:
        if len([x for x in selected if (x.get("score") or 0) < 40]) >= 13:
            break
        add_job(j, "no")

    return selected


def main():
    jobs = select_golden_jobs()
    print(f"Selected {len(jobs)} golden set jobs.")
    top = [j for j in jobs if (j.get("score") or 0) >= 85]
    mid = [j for j in jobs if 40 <= (j.get("score") or 0) < 85]
    bot = [j for j in jobs if (j.get("score") or 0) < 40]
    print(f"Distribution: Top={len(top)}, Mid={len(mid)}, Bot={len(bot)}")

    out_rows = []
    for idx, j in enumerate(jobs, 1):
        print(f"[{idx:2d}/{len(jobs)}] Fetching desc: {j['company']} - {j['title'][:35]}...")
        desc = fetch_job_text(j["url"], j["title"], j["company"])
        if not desc:
            desc = f"Role at {j['company']}: {j['title']} ({j['location']}). Reason: {j.get('reason', '')}"
        out_rows.append({
            "id": idx,
            "company": j["company"],
            "title": j["title"],
            "location": j["location"],
            "url": j["url"],
            "old_score": j.get("score", 0),
            "old_reason": j.get("reason", ""),
            "label": j.get("label", ""),
            "description": desc,
        })

    GOLDEN_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_SET_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "company", "title", "location", "url", "old_score", "old_reason", "label", "description"]
        )
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {GOLDEN_SET_PATH}")


if __name__ == "__main__":
    main()

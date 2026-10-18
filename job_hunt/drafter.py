import re
from datetime import datetime
from pathlib import Path

from job_hunt.db import get_job_by_url, last_scan_jobs
from job_hunt.keywords import gap_report, keyword_gaps
from job_hunt.llm_utils import MAX_DESCRIPTION_CHARS, chat_with_llm
from job_hunt.log import get_logger

logger = get_logger()

DRAFTS_DIR = Path("output") / "drafts"       # (T130; before, output/<company>-<date>/)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _resolve_job(job_ref: str) -> tuple[str, str]:
    """(url, company slug) for `#N` / `N` (job N of the last completed scan in data/jobs.db, best score first, so
    CSV row N of that scan; T31) or a URL (used as given)."""
    if job_ref.startswith("http"):
        return job_ref, "company"

    jobs = last_scan_jobs()
    if jobs is None:
        raise FileNotFoundError("No scan results found. Run: autopilot scan")

    idx = int(re.sub(r"\D", "", job_ref)) - 1
    if idx < 0 or idx >= len(jobs):
        raise ValueError(f"Job #{idx + 1} not in last scan (found {len(jobs)} jobs)")

    job = jobs[idx]
    logger.debug(f"Resolved job #{idx + 1}: '{job.get('title')}' @ {job.get('company')} — {job.get('url')}")
    return job["url"], _slug(job.get("company", "company"))


def _job_description(url: str, jd_file: str | None) -> tuple[str, str | None]:
    """The text of the posting and, when known, its company: from --jd-file, else the database (T29/T40)."""
    if jd_file:
        return Path(jd_file).read_text(encoding="utf-8"), None
    row = get_job_by_url(url)
    if row is None:
        raise RuntimeError(
            f"This job is not in the database: {url}\n"
            "Run a scan that finds it, or paste its description into a file and pass --jd-file FILE."
        )
    if not (row.get("description") or "").strip():
        raise RuntimeError(
            f"The database has no stored description for {url} (it was scanned before descriptions were kept).\n"
            "Re-run a scan, or pass the description with --jd-file FILE."
        )
    return row["description"], row.get("company")


def draft_application(config: dict, job_ref: str, jd_file: str | None = None) -> Path:
    cand = config.get("candidate", {})
    candidate_name = cand.get("name", "the candidate")
    resume_path = Path(cand.get("resume_path", "resume/YOUR_RESUME.md"))
    resume = resume_path.read_text()
    relocation_note = cand.get("relocation_note", "")
    logger.debug(f"Resume loaded: {resume_path} ({len(resume)} chars)")

    job_url, company_slug = _resolve_job(job_ref)

    jd, db_company = _job_description(job_url, jd_file)
    if db_company and company_slug == "company":
        company_slug = _slug(db_company)
    jd_truncated = jd[:MAX_DESCRIPTION_CHARS]   # requirements usually follow the company blurb: never cut at 4,000
    logger.debug(f"JD: {len(jd)} chars (using {len(jd_truncated)} for prompts)")

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = DRAFTS_DIR / f"{company_slug}-{date_str}"
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Output directory: {out_dir.resolve()}")

    # What the posting names that the resume does not (T44): no LLM call, so it is written even if a call fails.
    gaps = keyword_gaps(jd, resume)
    (out_dir / "keyword_gaps.txt").write_text(gap_report(gaps, job_url), encoding="utf-8")
    logger.info(f"In the posting, not in your resume: {', '.join(gaps['missing']) or 'nothing from the vocabulary'}"
                f"  (in both: {len(gaps['matched'])}; {out_dir / 'keyword_gaps.txt'})")

    logger.info("Tailoring resume...")
    resume_md = chat_with_llm(
        config,
        messages=[{"role": "user", "content": f"""Rewrite the resume below to mirror the language and emphasized skills in this job description.

Rules:
- Keep every fact truthful — do NOT invent experience
- Mirror JD terminology where the candidate genuinely has that experience
- Reorder projects/bullets to surface most relevant experience first
- Keep the same section structure
- Output full resume in Markdown

JOB DESCRIPTION:
{jd_truncated}

ORIGINAL RESUME:
{resume}

Output ONLY the tailored resume in Markdown. No preamble."""}],
        temperature=0.2,
    )
    tailored_resume_path = out_dir / f"resume_{company_slug}.md"
    tailored_resume_path.write_text(resume_md)
    logger.info(f"  Saved: {tailored_resume_path} ({len(resume_md)} chars)")

    logger.info("Drafting cover letter...")
    relocation_line = f"- {relocation_note}" if relocation_note else ""
    cover_md = chat_with_llm(
        config,
        messages=[{"role": "user", "content": f"""Write a one-page cover letter for {candidate_name} applying to this role.

Rules:
- Open with one specific reason this role fits {candidate_name} (reference something concrete in the JD)
- Paragraph 1: most relevant experience (2-3 sentences)
- Paragraph 2: why this company specifically (not generic)
- Close: clear ask for an interview
- Tone: direct and confident, not obsequious
{relocation_line}
- Do NOT use: "I am excited to apply", "I am a team player", "I am passionate about"

JOB DESCRIPTION:
{jd_truncated}

CANDIDATE RESUME:
{resume}

Output ONLY the cover letter. No preamble."""}],
        temperature=0.3,
    )
    cover_path = out_dir / f"cover_letter_{company_slug}.md"
    cover_path.write_text(cover_md)
    logger.info(f"  Saved: {cover_path} ({len(cover_md)} chars)")

    logger.info("Extracting application info...")
    info_txt = chat_with_llm(
        config,
        messages=[{"role": "user", "content": f"""Extract from this job posting (plain text output, clear labels):

1. Application URL or email
2. Hiring manager / recruiter name (if mentioned)
3. "Contact for questions" info (if mentioned)
4. Application deadline (if mentioned)
5. Key requirements (bullet list, max 8 items)
6. Nice-to-have skills (bullet list, max 5 items)

JOB DESCRIPTION:
{jd_truncated}"""}],
        temperature=0.1,
    )
    info_path = out_dir / "application_info.txt"
    info_path.write_text(f"Source URL: {job_url}\n\n{info_txt}")
    logger.info(f"  Saved: {info_path}")

    logger.info(f"\nAll files in: {out_dir.resolve()}")
    logger.info("Review, edit, then submit manually.")
    return out_dir

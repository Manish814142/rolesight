"""First-time setup (T103): `rolesight init [--resume FILE] [--yes]` and `rolesight check-filter`.

`init` copies the templates into the working directory. With `--resume`, one Gemini call reads the resume and drafts the
person's settings: name, profile, what they seek and what is not for them (config.json candidate.*), the title filter
(candidate.titles) and the scoring rubric (rubric.md, the built-in one rewritten for this person). A PDF resume is first
turned into Markdown by Gemini (resume/<name>.md). Nothing is applied for the user: every value is written where they can
read and edit it, and an existing config.json or rubric.md is kept as a .bak copy.
"""
from __future__ import annotations

import argparse
import getpass
import importlib.resources as pkg_resources
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from job_hunt.llm_utils import DEFAULT_SCORING_RUBRIC, _gemini_models, _get_genai_client_and_types
from job_hunt.log import redact
from job_hunt.models import JobPosting
from job_hunt.prefilter import (
    DEFAULT_TITLE_EXCEPTIONS,
    DEFAULT_TITLE_EXCLUDE,
    DEFAULT_TITLE_INCLUDE,
    MAX_TITLE_TERM_LENGTH,
    TitleRules,
    TitleRulesError,
    _alternation,
    configure_titles,
    should_evaluate_job,
)
from job_hunt.settings import load_env_file

RUBRIC_FILE = "rubric.md"
RESUME_SUFFIXES = (".md", ".markdown", ".txt", ".pdf")
API_KEY_URL = "https://aistudio.google.com/apikey"
_TERM_OK = re.compile(r"^[\w .+#/&'-]+$")
# The eight rule headings of the built-in rubric. A drafted rubric must keep every one of them word for word (the caps
# and the scoring bands live in them); only the facts about the candidate under them may change.
RUBRIC_HEADINGS = re.findall(r"^\d\. [^\n]+:$", DEFAULT_SCORING_RUBRIC, re.MULTILINE)


# -- plain `init`: the templates -----------------------------------------------------------------------------------------

def _scaffold(cwd: Path) -> bool:
    """Copy the templates that are missing; True when config.json was created now."""
    data = pkg_resources.files("job_hunt.data")

    def copy(src: str, dest: Path, label: str) -> bool:
        if dest.exists():
            print(f"  {dest.name} already exists, skipping")
            return False
        dest.write_text(data.joinpath(src).read_text(encoding="utf-8"), encoding="utf-8")
        print(f"✓ {label}")
        return True

    copy("companies.json", cwd / "companies.json", "companies.json created (200+ companies with a live job board, mostly hiring in India)")
    created = copy("config.example.json", cwd / "config.json", "config.json created — your settings")
    copy("env_example", cwd / ".env", ".env created — your Gemini API key goes here")
    rubric = cwd / RUBRIC_FILE
    if rubric.exists():
        print(f"  {RUBRIC_FILE} already exists, skipping")
    else:
        rubric.write_text(DEFAULT_SCORING_RUBRIC + "\n", encoding="utf-8")
        print(f"✓ {RUBRIC_FILE} created — how Gemini scores a job against you (the built-in rubric until you change it)")
    (cwd / "resume").mkdir(exist_ok=True)
    copy("resume_template.md", cwd / "resume" / "YOUR_RESUME.md", "resume/YOUR_RESUME.md created — or use your own file")
    (cwd / "output").mkdir(exist_ok=True)
    return created


def _template_candidate() -> Dict[str, Any]:
    data = pkg_resources.files("job_hunt.data")
    return json.loads(data.joinpath("config.example.json").read_text(encoding="utf-8"))["candidate"]


# -- the Gemini calls ---------------------------------------------------------------------------------------------------

def _is_placeholder(value: Optional[str]) -> bool:
    v = (value or "").strip()
    return not v or v.startswith("YOUR_") or v.lower().endswith("_here")


def _api_key(cwd: Path) -> Optional[str]:
    """GEMINI_API_KEY from .env (which wins, as in a scan) or the environment; asked for on a terminal and saved to .env."""
    env_file = cwd / ".env"
    if env_file.exists():
        load_env_file(env_file)
    key = os.getenv("GEMINI_API_KEY")
    if not _is_placeholder(key):
        return key
    if not sys.stdin.isatty():
        return None
    print(f"\nA Gemini API key is needed to read your resume (free: {API_KEY_URL}).")
    key = getpass.getpass("Paste it here (it is saved to .env, not shown): ").strip()
    if _is_placeholder(key):
        return None
    _save_key(env_file, key)
    os.environ["GEMINI_API_KEY"] = key
    return key


def _save_key(env_file: Path, key: str) -> None:
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    out, done = [], False
    for line in lines:
        if re.match(r"\s*#?\s*GEMINI_API_KEY\s*=", line) and not done:
            out.append(f'GEMINI_API_KEY="{key}"')
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f'GEMINI_API_KEY="{key}"')
    env_file.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("✓ key saved to .env")


def _models(cwd: Path) -> List[str]:
    config: Dict[str, Any] = {}
    try:
        config = json.loads((cwd / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if os.getenv("GEMINI_MODEL") and not _is_placeholder(os.getenv("GEMINI_MODEL")):
        config["gemini_model"] = os.getenv("GEMINI_MODEL")
    return _gemini_models(config)


def _generate(api_key: str, models: List[str], contents: List[Any], schema: Optional[dict] = None) -> str:
    """One Gemini answer as text, trying the models in order. The error names the model, never the key."""
    client, types = _get_genai_client_and_types(api_key)
    kwargs: Dict[str, Any] = {"temperature": 0.2}
    if schema:
        kwargs.update(response_mime_type="application/json", response_json_schema=schema)
    last = ""
    for model in models:
        try:
            parts = [types.Part.from_bytes(data=c, mime_type="application/pdf") if isinstance(c, bytes) else c for c in contents]
            resp = client.models.generate_content(model=model, contents=parts, config=types.GenerateContentConfig(**kwargs))
            if resp.text and resp.text.strip():
                return resp.text
            last = f"{model}: empty answer"
        except Exception as e:  # noqa: BLE001 - every model failed is reported below
            last = f"{model}: {redact(str(e), api_key)[:200]}"
    raise RuntimeError(f"Gemini did not answer ({last})")


PDF_PROMPT = ("Transcribe this resume into Markdown. Keep every fact: name, contact line, summary, skills, every job with its "
              "dates and bullet points, projects, education. Use headings and bullet lists. Do not add, judge or summarise "
              "anything. Answer with the Markdown only.")

DRAFT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "profile": {"type": "string"},
        "seeking": {"type": "string"},
        "not_suitable": {"type": "string"},
        "jobs": {"type": "array", "items": {"type": "object", "properties": {
            "company": {"type": "string"}, "title": {"type": "string"},
            "start": {"type": "string"}, "end": {"type": "string"}}, "required": ["company", "start", "end"]}},
        "include": {"type": "array", "items": {"type": "string"}},
        "exclude": {"type": "array", "items": {"type": "string"}},
        "generic_engineer_titles": {"type": "boolean"},
    },
    "required": ["name", "profile", "seeking", "not_suitable", "jobs", "include", "exclude", "generic_engineer_titles"],
}
# Single words that would let nearly every title through; the generic-engineer switch covers bare "Engineer" titles.
TOO_BROAD = {"engineer", "engineers", "engineering", "developer engineer"}


def _draft_prompt(resume: str, today: str) -> str:
    example = {"include": list(DEFAULT_TITLE_INCLUDE), "exclude": list(DEFAULT_TITLE_EXCLUDE)}
    return f"""You set up a job radar for the person whose resume is below. It fetches jobs from company boards (mostly in India),
drops those whose TITLE does not fit, and asks an AI to score the rest against the resume. Today is {today}.
Draft this person's settings as JSON:

- name: their name as on the resume.
- jobs: every job and internship on the resume, each with company, title, start and end as "YYYY-MM" (a month name or
  number from the resume; "Nov 2023" is "2023-11"); end is "present" for a current role. Copy the dates, do not compute.
- profile: one line, years of experience and core stack, e.g. "3 YOE backend engineer. Stack: Node.js, TypeScript, MongoDB, AWS".
- seeking: one line, the roles and work arrangement they would want, judged from the resume (e.g. "Backend or platform roles,
  remote or hybrid in Bengaluru"). If the resume names a city, use it; otherwise say "anywhere in India or remote".
- not_suitable: one line, roles that are clearly not for them (e.g. "Pure frontend, QA, support, management, internships").
- include: 10 to 40 lower-case words or short phrases; a job title must contain one of them to be scored. Use the role names
  this person would apply to and their variants ("node", "nodejs", "node.js"). Matching is whole-word and case-insensitive;
  spaces and hyphens inside an entry are optional ("back end" also matches "Back-End" and "backend"). Never a bare
  "engineer": bare engineer titles are what generic_engineer_titles is for.
- exclude: 20 to 80 lower-case words or phrases; a title containing one is dropped before scoring: seniority levels far above
  this person (e.g. "principal", "director" for someone with 3 years), role families they do not do, and technologies or
  languages they do not have when a title names them (e.g. "java" for a Node.js developer). Never exclude a word that is part
  of one of their own include entries.
- generic_engineer_titles: true if this person is a software engineer (then bare titles like "Senior Engineer" or
  "Engineer II" are scored too), else false.

Use only words and the symbols . + # / & - in include and exclude. START FROM THIS WORKED EXAMPLE, the tested lists of a
3-year Node.js / TypeScript / Python backend engineer in India, and adapt it to this person: keep what fits them, remove
what they do (a Java developer must not exclude "java"; a frontend developer must not exclude "react" or "front end"),
add the role names and the technologies of their own field, and exclude the languages, platforms and role families
they do not have. For someone whose field is close to the example, most entries stay:
{json.dumps(example)}

THE RESUME:
{resume}
"""


def _rubric_prompt(resume: str, profile: str, years: float, today: str) -> str:
    return f"""Below is a scoring rubric an AI uses to score job postings against one candidate (a 3.3-year Node.js / TypeScript /
Python backend engineer). Rewrite it for the candidate whose resume follows. Today is {today}.
This candidate has about {years:g} years of professional experience; their profile: {profile}

Keep every line that starts with a rule number ("1. ", "2. ", ... "8. ") exactly as it is, word for word, with its cap,
and keep the line breaks and the indentation. Change only the facts about the candidate under the headings: the years
(use {years:g}) and the seniority bands that follow from them (rules 3, 5 and 7), the core stack and the languages that
count as theirs or as outside theirs, with fitting examples (rules 4 and 5), the kind of fit in rule 6, and the domains or
tools they have or lack (rule 8). In rule 4, every language the original lists as outside the stack stays outside unless
this resume shows it. Leave rule 1 (India) as it is. Answer with the rubric text only, no comments.

THE RUBRIC:
{DEFAULT_SCORING_RUBRIC}

THE RESUME:
{resume}
"""


def _month(value: str, today: date) -> Optional[int]:
    v = str(value or "").strip().lower()
    if v in ("present", "current", "now", "today", "ongoing"):
        return today.year * 12 + today.month - 1
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", v)
    if not m or not 1 <= int(m.group(2)) <= 12:
        return None
    return int(m.group(1)) * 12 + int(m.group(2)) - 1


def years_of_experience(jobs: Any, today: date) -> Optional[float]:
    """Years covered by the resume's jobs, counted in months: each job from its start to its end month (both counted),
    overlaps once, internships at their real length, "present" = this month. The model reads the dates; the sum is code
    (2026-10-14: asked for the number itself, it said 1.5 and 5 for a 3.3-year resume)."""
    months: set = set()
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, dict):
            continue
        start, end = _month(job.get("start", ""), today), _month(job.get("end", ""), today)
        if start is None or end is None or end < start:
            continue
        months.update(range(start, min(end, today.year * 12 + today.month - 1) + 1))
    return round(len(months) / 12, 1) if months else None


def normalise_rubric(text: str) -> str:
    """Undo cosmetic changes around an unchanged heading (code fences, **bold**, indentation) before it is checked."""
    text = re.sub(r"^```\w*\s*|\s*```$", "", text.strip())
    headings = set(RUBRIC_HEADINGS)
    lines = []
    for line in text.splitlines():
        bare = line.strip().strip("*").strip()
        lines.append(bare if bare in headings else line.rstrip())
    return "\n".join(lines).strip()


# -- cleaning a draft -----------------------------------------------------------------------------------------------------

def _clean_terms(values: Any, label: str, notes: List[str]) -> List[str]:
    out: List[str] = []
    for v in values if isinstance(values, list) else []:
        term = str(v).strip().lower()
        if not term or term in out:
            continue
        if len(term) > MAX_TITLE_TERM_LENGTH or not _TERM_OK.match(term):
            notes.append(f"dropped the {label} entry {term!r} (use words and . + # / & - only)")
            continue
        out.append(term)
    return out


def rubric_problems(text: str) -> List[str]:
    """Why a drafted rubric cannot be used as it is: the rule headings it lost or changed."""
    if not text.strip().startswith("SCORING RUBRIC"):
        return ["it does not start with 'SCORING RUBRIC'"]
    lines = set(text.splitlines())
    return [f"the heading {h!r} is missing or changed" for h in RUBRIC_HEADINGS if h not in lines]


def clean_draft(draft: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    """The settings to write and what was changed on the way, as notes for the user."""
    notes: List[str] = []
    include = _clean_terms(draft.get("include"), "include", notes)
    broad = [t for t in include if t in TOO_BROAD]
    if broad:
        include = [t for t in include if t not in TOO_BROAD]
        notes.append(f"dropped {', '.join(broad)} from include: it would let nearly every title through "
                     "(bare 'Engineer' titles are covered by generic_engineer_titles)")
    exclude = _clean_terms(draft.get("exclude"), "exclude", notes)
    generic = bool(draft.get("generic_engineer_titles"))
    if not include:
        include = list(DEFAULT_TITLE_INCLUDE)
        notes.append("Gemini proposed no include words; the defaults are kept: edit candidate.titles.include")
    blocking = blocking_excludes(include, exclude)
    if blocking:
        exclude = [t for t in exclude if t not in blocking]
        notes.append(f"removed from exclude because your own include words contain them: {', '.join(sorted(blocking))}")
    rubric = normalise_rubric(str(draft.get("rubric") or ""))
    problems = rubric_problems(rubric)
    if problems:
        notes.append("the drafted rubric changed the rules themselves (" + "; ".join(problems[:2]) +
                     f"), so {RUBRIC_FILE} has the built-in rubric: edit its facts about the candidate yourself")
        rubric = DEFAULT_SCORING_RUBRIC
    raw_years = draft.get("years_of_experience")
    years = round(float(raw_years), 1) if isinstance(raw_years, (int, float)) and raw_years > 0 else None
    settings: Dict[str, Any] = {
        "name": str(draft.get("name") or "").strip() or "Your Name",
        "years": years,
        "jobs": draft.get("jobs") if isinstance(draft.get("jobs"), list) else [],
        "profile": " ".join(str(draft.get("profile") or "").split()),
        "seeking": " ".join(str(draft.get("seeking") or "").split()),
        "not_suitable": " ".join(str(draft.get("not_suitable") or "").split()),
        "titles": {"include": include, "exclude": exclude, "exceptions": list(DEFAULT_TITLE_EXCEPTIONS),
                   "generic_engineer_titles": generic},
        "rubric": rubric,
    }
    return settings, notes


def blocking_excludes(include: List[str], exclude: List[str]) -> set:
    """Exclude entries that would reject one of the person's own include entries (the default exceptions applied)."""
    exceptions = _alternation(DEFAULT_TITLE_EXCEPTIONS)
    out = set()
    for term in exclude:
        pattern = _alternation((term,))
        if pattern and any(pattern.search(exceptions.sub(" ", inc) if exceptions else inc) for inc in include):
            out.add(term)
    return out


# -- `init --resume` ---------------------------------------------------------------------------------------------------

def _relative(path: Path, cwd: Path) -> str:
    try:
        return str(path.resolve().relative_to(cwd.resolve()))
    except ValueError:
        return str(path.resolve())


def _backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    bak = path.with_name(path.name + ".bak")
    shutil.copy2(path, bak)
    return bak


def _confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def personalize(cwd: Path, resume: Path, config_was_created: bool, yes: bool,
                generate: Callable[..., str] = _generate) -> None:
    if not resume.is_file():
        sys.exit(f"No such resume file: {resume}")
    if resume.suffix.lower() not in RESUME_SUFFIXES:
        sys.exit(f"{resume.name}: use a .pdf, .md or .txt resume (from Word: File > Save as > PDF)")
    config_path = cwd / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"config.json cannot be read ({e}); fix or delete it and run `rolesight init --resume {resume}` again")
    candidate = config.setdefault("candidate", {})
    personal = not config_was_created and candidate != _template_candidate()
    if personal and not yes and not _confirm("config.json already has your settings. Replace the candidate part "
                                             "(the current file is kept as config.json.bak)?"):
        sys.exit("Nothing changed. Run again with --yes to replace the candidate settings in config.json "
                 "(a config.json.bak copy is kept).")

    key = _api_key(cwd)
    if not key:
        sys.exit(f"No Gemini API key. Put it in .env (GEMINI_API_KEY=...; free at {API_KEY_URL}) and run "
                 f"`rolesight init --resume {resume}` again.")
    models = _models(cwd)

    if resume.suffix.lower() == ".pdf":
        print(f"Reading {resume.name} (PDF) with Gemini…")
        text = generate(key, models, [resume.read_bytes(), PDF_PROMPT]).strip()
        text = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text)
        resume_md = cwd / "resume" / (re.sub(r"[^\w.-]+", "_", resume.stem) + ".md")
        resume_md.parent.mkdir(exist_ok=True)
        _backup(resume_md)
        resume_md.write_text(text + "\n", encoding="utf-8")
        print(f"✓ {_relative(resume_md, cwd)} written: check it, the scan sends this text with every job")
        resume_path = _relative(resume_md, cwd)
    else:
        text = resume.read_text(encoding="utf-8")
        resume_path = _relative(resume, cwd)
    if len(text.strip()) < 200:
        sys.exit(f"The resume text is only {len(text.strip())} characters; nothing to draft from.")

    today = date.today().isoformat()
    print("Drafting your settings with Gemini…")
    raw = generate(key, models, [_draft_prompt(text, today)], DRAFT_SCHEMA)
    try:
        draft = json.loads(raw)
    except ValueError:
        sys.exit("Gemini's answer was not the JSON asked for; run the command again.")
    years = years_of_experience(draft.get("jobs"), date.today())
    draft["years_of_experience"] = years
    if years:
        print("Rewriting the scoring rubric for you…")
        draft["rubric"] = generate(key, models, [_rubric_prompt(text, str(draft.get("profile") or ""), float(years), today)])
    settings, notes = clean_draft(draft)

    bak = _backup(config_path) if personal else None
    candidate.update({k: settings[k] for k in ("name", "profile", "seeking", "not_suitable", "titles")})
    candidate["resume_path"] = resume_path
    candidate["rubric_file"] = RUBRIC_FILE
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rubric_file = cwd / RUBRIC_FILE
    current = rubric_file.read_text(encoding="utf-8").strip() if rubric_file.exists() else ""
    rubric_bak = _backup(rubric_file) if current not in ("", settings["rubric"], DEFAULT_SCORING_RUBRIC) else None
    rubric_file.write_text(settings["rubric"] + "\n", encoding="utf-8")
    _summary(settings, resume_path, notes, bak, rubric_bak)


def _summary(settings: Dict[str, Any], resume_path: str, notes: List[str], bak: Optional[Path], rubric_bak: Optional[Path]) -> None:
    t = settings["titles"]
    print("\n✓ config.json updated" + (f" (previous version: {bak.name})" if bak else ""))
    print(f"    name:          {settings['name']}")
    print(f"    resume:        {resume_path}")
    if settings.get("years") is not None:
        print(f"    experience:    {settings['years']:g} years, from the dates of these jobs (rubric.md rules 3, 5 and 7 use it: check it)")
        for job in settings.get("jobs") or []:
            print(f"                   {job.get('start', '?')} to {job.get('end', '?')}  {job.get('title', '')} at {job.get('company', '')}"[:118])
    else:
        print("    experience:    could not be counted from the resume's dates: rubric.md keeps the built-in years (3.3); edit rule 3")
    print(f"    profile:       {settings['profile']}")
    print(f"    seeking:       {settings['seeking']}")
    print(f"    not suitable:  {settings['not_suitable']}")
    print(f"    titles kept:    {len(t['include'])} words, e.g. {', '.join(t['include'][:8])}")
    print(f"    titles dropped: {len(t['exclude'])} words, e.g. {', '.join(t['exclude'][:8])}")
    print(f"    generic 'Senior Engineer' titles: {'scored' if t['generic_engineer_titles'] else 'dropped'}")
    print(f"✓ {RUBRIC_FILE} written: how each job is scored against you" + (f" (previous version: {rubric_bak.name})" if rubric_bak else ""))
    for note in notes:
        print(f"  note: {note}")
    print("\nThis is a draft: read config.json (the candidate part) and rubric.md, and change anything that is not you.")
    print("Next:")
    print('  rolesight check-filter "Senior Backend Engineer" "Bengaluru, India"   # would this title be scored?')
    print("  rolesight doctor                                                    # key and network check")
    print("  rolesight scan --limit 5                                            # a first small scan")


def init_project(resume: Optional[str] = None, yes: bool = False) -> None:
    cwd = Path.cwd()
    created = _scaffold(cwd)
    if resume:
        personalize(cwd, Path(resume).expanduser(), created, yes)
        return
    print("\nNext:")
    print(f"  1. Put your Gemini API key in .env (free: {API_KEY_URL})")
    print("  2. rolesight init --resume path/to/your_resume.pdf   # drafts your profile, title filter and rubric.md from it")
    print("     (or edit config.json and rubric.md yourself: docs/00-user-guide.md explains every setting)")
    print("  3. rolesight scan")


def parse_init_args(argv: List[str]) -> Dict[str, Any]:
    ap = argparse.ArgumentParser(prog="rolesight init", description="Set up this directory; --resume drafts your settings.")
    ap.add_argument("--resume", help="your resume (.pdf, .md or .txt): drafts config.json's candidate part and rubric.md")
    ap.add_argument("--yes", action="store_true", help="replace existing candidate settings without asking (.bak copies kept)")
    args = ap.parse_args(argv)
    return {k: v for k, v in (("resume", args.resume), ("yes", args.yes)) if v}


# -- the settings a command reads when config.json is optional -----------------------------------------------------------

def optional_config(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """config.json if there is one (commands such as discover and check-filter also work without it)."""
    path = (cwd or Path.cwd()) / "config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"config.json is not valid JSON: {e}")


def configure_titles_or_exit(config: Dict[str, Any]) -> TitleRules:
    try:
        return configure_titles(config)
    except TitleRulesError as e:
        sys.exit(f"config.json: {e}")


def check_filter_command(argv: List[str]) -> None:
    """`rolesight check-filter TITLE [LOCATION] [--remote] [--cities "Pune, Mumbai"]`: KEPT or REJECTED with the reason,
    using config.json's title filter and cities when there is one. Local: no network, no key."""
    ap = argparse.ArgumentParser(prog="rolesight check-filter", description="Show what the pre-filter does with one job.")
    ap.add_argument("title", help='job title, e.g. "Java Developer"')
    ap.add_argument("location", nargs="?", default="", help='location as the board shows it, e.g. "Pune, India"')
    ap.add_argument("--remote", action="store_true", help="the board flags the job as remote")
    ap.add_argument("--cities", default=None, help='only these Indian cities, comma separated (default: config.json\'s cities)')
    args = ap.parse_args(argv)
    from job_hunt.settings import cities_of
    config = optional_config()
    rules = configure_titles_or_exit(config)
    cities = [c.strip() for c in args.cities.split(",") if c.strip()] if args.cities is not None else cities_of(config)
    job = JobPosting(global_id="check:1", ats="check", company="check", title=args.title, location=args.location,
                     is_remote=args.remote, url="https://example.com/check")
    kept, reason = should_evaluate_job(job, cities=cities)
    print("KEPT" if kept else f"REJECTED — {reason}")
    source = "config.json candidate.titles" if (config.get("candidate") or {}).get("titles") is not None else "the default title words"
    print(f"  (titles: {source}, {len(rules.include)} include / {len(rules.exclude)} exclude"
          f"{'; cities: ' + ', '.join(cities) if cities else ''})", file=sys.stderr)   # stdout stays one line for scripts

"""Defaults that more than one module reads, so the value lives in one place."""
from __future__ import annotations

import os
from pathlib import Path


def is_placeholder(value: str | None) -> bool:
    """A template value such as `your_gemini_api_key_here` or `YOUR_…`, or nothing: "not filled in"."""
    v = (value or "").strip()
    return not v or v.startswith("YOUR_") or v.endswith("_HERE") or v.endswith("_here")


def load_env_file(path: str | Path = ".env") -> None:
    """The .env values into os.environ, over the shell's, as load_dotenv(override=True) did, except a placeholder or empty
    value, which never replaces a real one (T103: the template .env written by `init` hid a key exported in the shell, so
    `init --resume` and every scan saw "your_gemini_api_key_here")."""
    from dotenv import dotenv_values
    for key, value in dotenv_values(Path(path)).items():
        if not is_placeholder(value):
            os.environ[key] = str(value)

# Score that counts as a match (Worth Applying, Telegram alerts, the digest, open_matches.csv). Manish chose 70 on
# 2026-10-10 (T05). On the 82 labelled jobs rubric v7 (T73, before T74's AI clause) passes no `no` job at 60 or at 70
# (2 runs); 70 drops at most one `maybe`. (The 92% vs 83% precision gap was the pre-T73 rubric's.) config.json's candidate.min_score
# is the one place that changes it; a MIN_SCORE environment variable still overrides it for a single run.
DEFAULT_MIN_SCORE = 70


def min_score_of(config: dict) -> int:
    return int((config.get("candidate") or {}).get("min_score", DEFAULT_MIN_SCORE))

# Only jobs posted in the last N days are scored (T02: Manish asked for a window on 2026-10-10 and named no number;
# 7 is Claude's choice until he confirms it). Jobs with no posted date are never
# filtered. config.json's candidate.max_posted_age_days changes it (JSON null switches the window off);
# `autopilot scan --posted-within N|all` overrides it for one run. Adapters also use it to stop paging early.
DEFAULT_MAX_POSTED_AGE_DAYS = 7


def max_posted_age_of(config: dict) -> int | None:
    candidate = config.get("candidate") or {}
    if "max_posted_age_days" not in candidate:
        return DEFAULT_MAX_POSTED_AGE_DAYS
    value = candidate["max_posted_age_days"]
    return None if value is None else int(value)


# Optional (T84): config.json candidate.cities narrows the India location check to these cities. Absent or empty means all of
# India, which is what Manish uses (2026-10-14). A list, or one comma-separated string.
def cities_of(config: dict) -> list[str]:
    return _names((config.get("candidate") or {}).get("cities"))


def _names(value) -> list[str]:
    """A list, or one comma-separated string, as distinct trimmed names (case-insensitive)."""
    if not value:
        return []
    items = value.split(",") if isinstance(value, str) else list(value)
    names: list[str] = []
    for item in items:
        name = str(item).strip()
        if name and name.lower() not in {c.lower() for c in names}:
            names.append(name)
    return names


# T136 (T108): config.json candidate.countries, where to look (default India alone: the original rules), and
# candidate.home_country, where the person lives (default India): a job in another country needs a work visa.
def countries_of(config: dict) -> list[str]:
    return _names((config.get("candidate") or {}).get("countries"))


def home_country_of(config: dict) -> str:
    return str((config.get("candidate") or {}).get("home_country") or "").strip() or "India"

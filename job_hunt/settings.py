"""Defaults that more than one module reads, so the value lives in one place."""
from __future__ import annotations

# Score that counts as a match (Worth Applying, Telegram alerts, the digest, open_matches.csv). Manish chose 70 on
# 2026-10-10 (T05): 92% precision on the 82 labelled jobs at 70 against 86% at 60. config.json's candidate.min_score
# is the one place that changes it; a MIN_SCORE environment variable still overrides it for a single run.
DEFAULT_MIN_SCORE = 70


def min_score_of(config: dict) -> int:
    return int((config.get("candidate") or {}).get("min_score", DEFAULT_MIN_SCORE))

# Only jobs posted in the last N days are scored (T02, Manish 2026-10-10). Jobs with no posted date are never
# filtered. config.json's candidate.max_posted_age_days changes it (JSON null switches the window off);
# `autopilot scan --posted-within N|all` overrides it for one run. Adapters also use it to stop paging early.
DEFAULT_MAX_POSTED_AGE_DAYS = 7


def max_posted_age_of(config: dict) -> int | None:
    candidate = config.get("candidate") or {}
    if "max_posted_age_days" not in candidate:
        return DEFAULT_MAX_POSTED_AGE_DAYS
    value = candidate["max_posted_age_days"]
    return None if value is None else int(value)

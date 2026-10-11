"""Defaults that more than one module reads, so the value lives in one place."""
from __future__ import annotations

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

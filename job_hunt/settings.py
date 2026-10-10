"""Defaults that more than one module reads, so the value lives in one place."""
from __future__ import annotations

# Score that counts as a match (Worth Applying, Telegram alerts, the digest, open_matches.csv). Manish chose 70 on
# 2026-10-10 (T05): 92% precision on the 82 labelled jobs at 70 against 86% at 60. config.json's candidate.min_score
# is the one place that changes it; a MIN_SCORE environment variable still overrides it for a single run.
DEFAULT_MIN_SCORE = 70


def min_score_of(config: dict) -> int:
    return int((config.get("candidate") or {}).get("min_score", DEFAULT_MIN_SCORE))

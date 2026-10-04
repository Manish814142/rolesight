"""Posted-date parsing and the optional 'posted within N days' scan filter."""
from __future__ import annotations

from datetime import date

import pytest

from job_hunt.prefilter import is_too_old, posted_age_days

TODAY = date(2026, 10, 4)


@pytest.mark.parametrize("posted,age", [
    ("2026-10-01T09:00:00Z", 3),                 # Greenhouse / Ashby / SmartRecruiters ISO
    ("2026-09-03T13:30:34-04:00", 31),
    ("2026-10-04", 0),                           # Workable date
    ("1790985600000", 0),                        # Lever epoch-ms fallback string (2026-10-03T00:00Z)
    ("Posted Today", 0),                         # Workday relative text
    ("Posted Yesterday", 1),
    ("Posted 5 Days Ago", 5),
    ("Posted 30+ Days Ago", 30),                 # lower bound: at least 30
    ("", None),
    ("sometime last month", None),
])
def test_posted_age_days(posted, age):
    got = posted_age_days(posted, today=TODAY)
    if posted == "1790985600000":
        assert got in (0, 1)                     # epoch boundary vs local date
    else:
        assert got == age


def test_unknown_date_is_never_too_old():
    """Jobs without a posted date are kept for manual review, never filtered out."""
    assert is_too_old("", 1, today=TODAY) is False
    assert is_too_old("garbage", 1, today=TODAY) is False


def test_is_too_old_threshold_and_disabled():
    assert is_too_old("2026-09-30", 3, today=TODAY) is True     # 4 days old
    assert is_too_old("2026-10-01", 3, today=TODAY) is False    # exactly 3 days: kept
    assert is_too_old("Posted 30+ Days Ago", 7, today=TODAY) is True
    assert is_too_old("2020-01-01", None, today=TODAY) is False  # filter off

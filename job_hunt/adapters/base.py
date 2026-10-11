"""Common base utilities and headers for direct ATS adapters."""
from __future__ import annotations

import html
import re
import threading
import time
from typing import Any, Dict, Iterable, Optional

import requests

from job_hunt.prefilter import is_too_old

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


_ESCAPED_TAG_RE = re.compile(r"&lt;\s*/?\s*[a-zA-Z]")
_BLOCK_TAG_RE = re.compile(r"<\s*/?\s*(br|p|div|li|ul|ol|h[1-6]|tr|table|section)\b[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(html_content: str) -> str:
    """Plain text from an HTML description, one line per block element.

    Greenhouse sends the markup itself entity-escaped ("&lt;p&gt;..."); such a document
    (escaped tags, no real ones) is decoded to real markup first. Stdlib only: bs4 is
    not a dependency, and its get_text() would keep escaped markup as literal text.
    """
    if not html_content:
        return ""
    text = html_content
    if "<" not in text and _ESCAPED_TAG_RE.search(text):
        text = html.unescape(text)
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = html.unescape(_TAG_RE.sub(" ", text))
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


# Total wall-clock budget for one HTTP response (connect + full body). requests'
# `timeout` is per socket read, so a server trickling bytes never trips it — on
# 2026-10-04 single Lever boards took 100-436 s. This bounds every call; it is generous
# on purpose (completeness over speed) — fetches run in parallel, so one slow board only
# occupies one worker.
DOWNLOAD_DEADLINE_SECONDS = 900.0


class DeadlineExceeded(Exception):
    """An HTTP response was still downloading when its total deadline passed."""


def _request(method: str, url: str, deadline: float, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", 15)
    start = time.monotonic()
    send = requests.get if method == "GET" else requests.post
    resp = send(url, stream=True, **kwargs)
    try:
        chunks = []
        for chunk in resp.iter_content(chunk_size=65536):
            chunks.append(chunk)
            if time.monotonic() - start > deadline:
                raise DeadlineExceeded(f"{url} still downloading after {deadline:.0f}s")
        resp._content = b"".join(chunks)
    finally:
        resp.close()
    return resp


def http_get(url: str, deadline: float = DOWNLOAD_DEADLINE_SECONDS, **kwargs: Any) -> requests.Response:
    """requests.get with a hard total deadline; the body is fully read on return."""
    return _request("GET", url, deadline, **kwargs)


def http_post(url: str, deadline: float = DOWNLOAD_DEADLINE_SECONDS, **kwargs: Any) -> requests.Response:
    """requests.post with a hard total deadline; the body is fully read on return."""
    return _request("POST", url, deadline, **kwargs)


# Did the current fetch stop before the board's end? (T33 review) A paged adapter that keeps earlier pages after a
# failure, runs out of its time budget or stops at its job cap returns a subset: jobs it did not return may well still
# be open, so the scanner must not count them as missed. Per thread: the scanner fetches boards in a thread pool, and
# each adapter fetches one board within one thread.
_fetch_state = threading.local()


def begin_fetch(max_age_days: Optional[int] = None) -> None:
    """Call before fetching one board. `max_age_days` is the scan's posted-date window (T02), or None for no window."""
    _fetch_state.incomplete = None
    _fetch_state.max_age_days = max_age_days


def fetch_window() -> Optional[int]:
    """The posted-date window (days) of the fetch in progress on this thread, or None."""
    return getattr(_fetch_state, "max_age_days", None)


def outside_window(posted_at: str) -> bool:
    """True when a window is set and this posted date is known and older than it (undated jobs are never old)."""
    return is_too_old(posted_at, fetch_window())


# The reason stop_at_window records. The scanner treats this stop differently from a failed page or a cap (T78).
WINDOW_STOP_REASON = "posted-date window"


def stop_at_window(posted_dates: Iterable[str]) -> bool:
    """For an adapter whose list is newest first (Amazon `sort=recent`, Oracle POSTING_DATES_DESC, Eightfold
    `sort_by=timestamp`, SmartRecruiters): call after each page with that page's posted dates. True when a window is set
    and every job of the page is dated and older than it, so every later page is older still; the fetch is then marked
    incomplete, because the jobs it did not read are old, not gone (T33 must not close them). A page with one job
    inside the window, or one undated job, never stops the fetch."""
    dates = list(posted_dates)
    if fetch_window() is None or not dates or not all(outside_window(d) for d in dates):
        return False
    mark_incomplete(WINDOW_STOP_REASON)
    return True


def mark_incomplete(reason: str) -> None:
    """An adapter stopped early ("page failed at offset 20", "budget", "cap 2000"); the first reason is kept."""
    if getattr(_fetch_state, "incomplete", None) is None:
        _fetch_state.incomplete = reason


def fetch_incomplete() -> Optional[str]:
    """Why the board fetched since begin_fetch() is incomplete, or None when it ended normally."""
    return getattr(_fetch_state, "incomplete", None)

"""Common base utilities and headers for direct ATS adapters."""
from __future__ import annotations

import re
import time
from typing import Any, Dict

import requests

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def strip_html(html_content: str) -> str:
    """Strip HTML markup from a description string."""
    if not html_content:
        return ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator="\n").strip()
    except Exception:
        # Fallback to regex tag stripping
        clean = re.sub(r"<[^>]+>", " ", html_content)
        return " ".join(clean.split()).strip()


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

"""Common base utilities and headers for direct ATS adapters."""
from __future__ import annotations

import re
from typing import Dict

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

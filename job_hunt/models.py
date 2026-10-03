"""Canonical models and hashing utilities for JobNotify."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class JobPosting:
    global_id: str
    ats: str
    company: str
    title: str
    location: str
    is_remote: bool
    url: str
    description_text: str = ""
    posted_at: str = ""
    headcount: str = "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def canonical_hash(title: str, company: str, location: str) -> str:
    """Compute deterministic MD5 hash based on normalized title, company, and location.

    MD5(title.lower().strip() + company.lower().strip() + location.lower().strip())
    """
    key = f"{title.lower().strip()}{company.lower().strip()}{location.lower().strip()}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def url_hash(url: str) -> str:
    """Compute MD5 hash of normalized URL."""
    return hashlib.md5(url.strip().encode("utf-8")).hexdigest()

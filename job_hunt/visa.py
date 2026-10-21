"""Visa sponsorship per job (T138, T108 part 3): what the posting says, then what the company's public record says.

Most postings never say (T133: 85-100% of engineering postings in the UK, Germany, the Netherlands, Ireland, the UAE and
Singapore), so a job outside the person's home country gets a note in the CSV's Visa column: the posting's own words first
(`wording`, pattern counts read by hand in T133: "refused" right 12 of 12, "offered" 10 of 12), then the company's record from
`job_hunt/data/visa_sponsors.json` (UK register, Dutch IND register, Irish permits, two community lists). A record says the
company can sponsor, not that this job is sponsored: 17 of the 44 UK companies whose postings refuse are licensed sponsors.
"""
from __future__ import annotations

import importlib.resources
import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from job_hunt.places import Places

# Refusal is checked first: "we do not sponsor visas" also contains "sponsor visas".
_REFUSED = [
    r"\b(not|unable to|cannot|can't|can not|won't|will not|do not|don't|does not|doesn't|are not able to|is not able to|"
    r"aren't able to|not in a position to)\s+(currently\s+|presently\s+)?(be\s+)?(able\s+to\s+)?(offer|provide|support|"
    r"sponsor|consider|facilitate)\w*\s+(\w+\s+){0,4}?(visas?|sponsorship|work permits?|immigration)",
    r"\bno\s+(visa\s+|immigration\s+)?sponsorship\b",
    r"\bwithout\s+(the\s+need\s+for\s+|requiring\s+|need\s+of\s+|needing\s+)?(\w+\s+){0,2}?(visa\s+)?sponsorship",
    r"\bsponsorship\s+(is\s+|will\s+)?(not|n't)\s+(be\s+)?(available|offered|provided|possible|supported)",
    r"\b(must|need to|needs to|should|required to)\s+(already\s+)?(have|hold|possess|be)\s+(\w+\s+){0,4}?(right to work|"
    r"work permit|work authori[sz]ation|eligib\w* to work|authori[sz]ed to work|permitted to work|entitled to work|"
    r"legally (able|allowed|authori[sz]ed) to work)",
    r"\b(right to work|work authori[sz]ation|work permit)\s+(in\s+(the\s+)?\w+(\s+\w+)?\s+)?(is\s+)?(required|essential|mandatory|a must)",
    r"\bnot\s+eligible\s+for\s+(\w+\s+){0,3}?(visa\s+)?sponsorship",
    r"\b(requires?|requiring)\s+(\w+\s+){0,3}?(to\s+)?(have|hold)\s+(\w+\s+){0,3}?(right to work|work authori[sz]ation|work permit)",
]
# US-style compliance boilerplate ("must be authorized to work in the country in which they apply"): no answer either way.
_BOILERPLATE = re.compile(r"authori[sz]ed to work in the country (in which|where) (they|you) (apply|are applying)", re.I)
_OFFERED = [
    r"\bvisa\s+(sponsorship|support|assistance|help|processing)\s+(is\s+|will\s+be\s+|can\s+be\s+)?(available|provided|"
    r"offered|possible|included)",
    r"\b(we|will|can|able to|happy to|do|does|offer|offers|provide|provides|including|includes)\s+(\w+\s+){0,3}?"
    r"(sponsor\w*|support|assist\w*|help)\s+(\w+\s+){0,3}?(visas?|work permits?|blue card)",
    r"\b(offer|offers|offering|provide|provides|providing|including|includes|with)\s+(\w+\s+){0,4}?(visa|immigration|"
    r"work permit)\s+(sponsorship|support|assistance)\b",
    r"\b(relocation|relocation package|relocation support)\s+(and|&)\s+visa\s+(sponsorship|support|assistance)\b",
    r"\bvisa\s+(sponsorship|support)\s+(where|if|when)\s+(needed|necessary|required|applicable|eligible)",
    r"\bsponsorship\s+(is\s+)?available",
]
_VISA_WORDS = r"\b(visas?(?!\s*(and|&|/|,)?\s*(mastercard|amex|card|inc\b|payments|direct))|visa sponsorship|" \
              r"sponsorship for (a |your )?(visa|work)|work permits?|right to work|work authori[sz]ation|authori[sz]ed to work|" \
              r"immigration (sponsorship|support|assistance)|blue card|highly skilled migrant|kennismigrant|employment pass)\b"
_RELOCATION_REFUSED = r"\b(no relocation|relocation (is\s+)?(not|n't)\s+(be\s+)?(available|offered|provided|possible|supported)|" \
                      r"(not|unable to|cannot|can't|do not|don't) (offer|provide|support)\w* relocation)"
_RELOCATION_OFFERED = r"\b(relocation\s+(support|assistance|package|bonus|allowance|budget|help|benefits?|stipend|is\s+" \
                      r"(available|offered|provided|possible))|(help|support|assist)\w*\s+(you\s+)?(with\s+)?(your\s+)?relocat\w+)"
_RESIDENCE_REQUIRED = r"\b(must|need to|needs to|required to|should)\s+(already\s+)?(be\s+)?(currently\s+)?(based|located|" \
                      r"living|reside|resident)\s+(in|within)\b"

REFUSED = [re.compile(p, re.I) for p in _REFUSED]
OFFERED = [re.compile(p, re.I) for p in _OFFERED]
VISA_WORDS = re.compile(_VISA_WORDS, re.I)
RELOCATION_REFUSED = re.compile(_RELOCATION_REFUSED, re.I)
RELOCATION_OFFERED = re.compile(_RELOCATION_OFFERED, re.I)
RESIDENCE_REQUIRED = re.compile(_RESIDENCE_REQUIRED, re.I)


def _first(patterns: List[re.Pattern], text: str) -> Optional[re.Match]:
    hits = [m for p in patterns if (m := p.search(text))]
    return min(hits, key=lambda m: m.start()) if hits else None


def wording(text: str) -> Tuple[str, str]:
    """("refused" | "offered" | "mentioned" | "silent", the matched sentence)."""
    t = text or ""
    for kind, pats in (("refused", REFUSED), ("offered", OFFERED)):
        m = _first(pats, t)
        if m and not (kind == "refused" and _BOILERPLATE.search(_sentence(t, m))):
            return kind, _sentence(t, m)
    m = VISA_WORDS.search(t)
    return ("mentioned", _sentence(t, m)) if m else ("silent", "")


def relocation_wording(text: str) -> str:
    t = text or ""
    if RELOCATION_REFUSED.search(t):
        return "refused"
    return "offered" if RELOCATION_OFFERED.search(t) else "silent"


def residence_required(text: str) -> bool:
    return bool(RESIDENCE_REQUIRED.search(text or ""))


def _sentence(text: str, m: re.Match, pad: int = 140) -> str:
    return " ".join(text[max(0, m.start() - pad): m.end() + pad].split())


# The record of one company for one country, as a short phrase.
_RECORD_SOURCE = {"United Kingdom": "uk", "Netherlands": "nl", "Ireland": "ie"}
_LABEL = {"refused": "Posting: no visa sponsorship", "offered": "Posting: offers visa sponsorship",
          "mentioned": "Posting: unclear", "silent": "Not stated"}


@lru_cache(maxsize=1)
def _records() -> Dict[str, List[Dict[str, Any]]]:
    try:
        text = importlib.resources.files("job_hunt.data").joinpath("visa_sponsors.json").read_text(encoding="utf-8")
        return json.loads(text).get("companies") or {}
    except (OSError, ValueError):
        return {}


def record(company: str, country: str) -> str:
    """What the public records say about `company` for `country` ("UK licensed sponsor", "Dutch recognised sponsor",
    "N Irish work permits 2025-26", "on a relocation list"), joined with "; ", or ""."""
    said: List[str] = []
    for ev in _records().get(company or "", []):
        source = ev.get("source")
        if source == "lists":
            said.append("on a relocation list")
        elif source == _RECORD_SOURCE.get(country):
            if source == "uk":
                said.append("UK licensed sponsor")
            elif source == "nl":
                said.append("Dutch recognised sponsor")
            elif source == "ie":
                years: Dict[str, int] = {}
                for counts in (ev.get("names") or {}).values():
                    for year, n in (counts or {}).items():
                        years[year] = years.get(year, 0) + int(n or 0)
                span = "-".join(sorted(years)) if len(years) > 1 else "".join(years)
                said.append(f"{sum(years.values())} Irish work permits {span}".strip())
    return "; ".join(dict.fromkeys(said))


def note(company: str, location: str, description: str, places: Places) -> str:
    """The Visa column for one job: "" when the job needs no visa (home country, remote with no place, India alone);
    else the posting's own words ("Posting: no visa sponsorship" / "Posting: offers visa sponsorship" / "Posting: unclear" /
    "Not stated"), then the company's record for the job's country, e.g. "Not stated; UK licensed sponsor"."""
    if (places.india_only() and places.home == "India") or not places.needs_visa(location):
        return ""
    kind, _ = wording(description or "")
    countries = places.countries_in(location)      # none is home: needs_visa said so
    if not countries:
        region = places.region_in(location)
        countries = [region] if region else []
    said = "; ".join(dict.fromkeys(r for r in (record(company, c.name) for c in countries) if r))
    return f"{_LABEL[kind]}; {said}" if said else _LABEL[kind]

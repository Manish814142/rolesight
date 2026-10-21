"""Visa sponsorship per job (T138, T108 part 3): what the posting says, then what the company's public record says.

Most postings never say (T133: 85-100% of engineering postings in the UK, Germany, the Netherlands, Ireland, the UAE and
Singapore), so a job outside the person's home country gets a note in the CSV's Visa column: the posting's own words first
(`wording`, pattern counts read by hand in T133: "refused" right 12 of 12, "offered" 10 of 12), then the company's record from
`job_hunt/data/visa_sponsors.json` (UK register, Dutch IND register, Irish permits, US H-1B approvals, Canada's positive LMIA
employers, community lists), then the country's own rule (COUNTRY_RULE) unless the posting refuses. A record says the
company can sponsor, not that this job is sponsored: 17 of the 44 UK companies whose postings refuse are licensed sponsors.
"""
from __future__ import annotations

import importlib.resources
import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from job_hunt.places import Places, all_countries

# Refusal is checked first: "we do not sponsor visas" also contains "sponsor visas".
_REFUSED = [
    r"\b(not|unable to|cannot|can't|can not|won't|will not|do not|don't|does not|doesn't|are not able to|is not able to|"
    r"aren't able to|not in a position to)\s+(currently\s+|presently\s+)?(be\s+)?(able\s+to\s+)?(offer|provide|support|"
    r"sponsor|consider|facilitate)\w*\s+(\w+\s+){0,4}?(visas?|sponsorship|work permits?|immigration)",
    r"\bno\s+(visa\s+|immigration\s+)?sponsorship\b",
    r"\bwithout\s+(the\s+need\s+for\s+|requiring\s+|need\s+of\s+|needing\s+)?(\w+\s+){0,2}?(visa\s+)?sponsorship",
    r"\bsponsorship\s+(is\s+|will\s+)?(not|n't)\s+(be\s+)?(available|offered|provided|possible|supported)",
    # "[\w.]+" here and in the citizenship rule (T143): "must already have unrestricted U.S. work authorization" has a dotted word.
    r"\b(must|need to|needs to|should|required to)\s+(already\s+)?(have|hold|possess|be)\s+([\w.]+\s+){0,4}?(right to work|"
    r"work permit|work authori[sz]ation|eligib\w* to work|authori[sz]ed to work|permitted to work|entitled to work|"
    r"legally (able|allowed|authori[sz]ed) to work)",
    r"\b(right to work|work authori[sz]ation|work permit)\s+(in\s+(the\s+)?\w+(\s+\w+)?\s+)?(is\s+)?(required|essential|mandatory|a must)",
    r"\bnot\s+(eligible|open)\s+(for|to)\s+(\w+\s+){0,3}?(visa\s+)?sponsorship",   # T143: Raydar "not open to visa sponsorship"
    r"\b(requires?|requiring)\s+(\w+\s+){0,3}?(to\s+)?(have|hold)\s+(\w+\s+){0,3}?(right to work|work authori[sz]ation|work permit)",
    # A citizenship or residence requirement (T140, the end-to-end run: Thoughtworks Singapore "requires the successful candidate
    # to be a Singapore Citizen or PR"; Capco "only Singapore Citizens and Singapore Permanent Residents (PRs) will be considered").
    r"\b(requires?|required|requiring|must be|must hold|must have|open only to|only open to|limited to|restricted to)\s+"
    r"([\w.]+\s+){0,8}?(citizens?|citizenship|permanent residents?|permanent residency|(?-i:PRs?))\b",   # "PR" upper case only: "pr ocess"
    r"\bonly\s+(\w+\s+){0,3}?(citizens?|permanent residents?)\b",
    # A nationals-only role (T141): Tamara Dubai "Emirati National required" (2026-10-21 fetch). The bare word "Emiratisation" is not
    # used: Infoprolearning's "support Emiratisation objectives through the training of UAE National employees" is a job duty.
    r"\b(nationals?|singaporeans?|emiratis?)\s+(only|required)\b",
    r"\bonly\s+(\w+\s+){0,2}?(nationals?|singaporeans?|emiratis?)\b",
    r"\b(open|restricted|limited|reserved)\s+(only\s+)?to\s+(\w+\s+){0,2}?(nationals?|singaporeans?|emiratis?)\b",
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
_VISA_WORDS = r"\b(visas?(?!\s*(and|&|/|,)?\s*(mastercard|amex|card|inc\b|payments|direct|ventures))|visa sponsorship|" \
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
_RECORD_SOURCE = {"United Kingdom": "uk", "Netherlands": "nl", "Ireland": "ie", "United States": "us", "Canada": "ca"}

# Germany, the UAE and Singapore publish no register of sponsoring employers (T141), because their rules make one unnecessary:
# what a silent posting there still tells you. Read on the official pages on 2026-10-21:
# - UAE, u.ae "Work visa": "The employer must apply for the standard work visa."; MOHRE (u.ae "Work permits"): "employers may not
#   recruit or employ any worker unless a work permit is issued in accordance with MoHRE procedures".
# - Singapore, MOM "Apply for an Employment Pass" (updated 15 June 2026): "You can apply for an Employment Pass online as an
#   employer or appointed employment agent"; the job must first be advertised on MyCareersFuture.
# - Germany, Federal Employment Agency "EU Blue Card" (issue 03/2026): the professional applies; no licence for the employer; the
#   regular card from EUR 50,700 a year needs no Agency approval, shortage occupations and career starters from EUR 45,934.20 do.
#
# T143, the USA, Canada, Australia and New Zealand, read on 2026-10-21 (their registers are a download in two cases: the H-1B
# approvals and Canada's positive LMIA employers, scripts/build_visa_sponsors.py):
# - USA, USCIS "H-1B Electronic Registration Process" (updated 09/21/2026): the employer ("prospective petitioner") registers,
#   "USCIS will conduct a weighted selection" for the 65,000 + 20,000 cap, and the FY 2027 cap is reached. USCIS "H-1B FAQ" (read
#   through a web search: uscis.gov refuses scripts): a $100,000 payment applies to petitions filed from 21 Sep 2025 for workers
#   outside the United States (a proclamation of September 2025); the D. Mass.
#   court vacated USCIS's guidance on 8 June 2026 (California v. Mullin), DHS appealed and "still plans to collect the payment"
#   if the order is lifted. USCIS "L-1A" (updated 08/31/2026): the worker must "generally have been working for a qualifying
#   organization abroad for one continuous year" in the last three: the route through a company's office in the home country.
# - Canada, ESDC "Hire a temporary foreign worker through the Global Talent Stream": an employer that needs an LMIA hires through
#   the TFWP (the stream aims at 10 business days); some permits need none (an intra-company transfer, for one), hence "usually".
#   IRCC "Express Entry: Federal Skilled Worker Program": a job offer is not required (the person applies, once invited).
# - Australia, Home Affairs "Becoming a sponsor" (quoted through a web search: the page refuses scripts): "Apply to become an approved sponsor, nominate the role ..., then nominate the
#   person you wish to employ" (Skills in Demand visa, subclass 482, since 7 Dec 2024); no public list of sponsors.
# - New Zealand, INZ "Overview of AEWV employer accreditation and job check": the employer must be accredited, then pass a job
#   check (the job advertised, no suitable New Zealander) before the person applies.
COUNTRY_RULE = {
    "United Arab Emirates": "UAE: the employer applies for the work visa",
    "Singapore": "Singapore: the employer applies for the Employment Pass",
    "Germany": "Germany: no sponsor licence needed (EU Blue Card)",
    "United States": "USA: from abroad, H-1B is a yearly lottery the employer enters (a $100,000 fee for it is in court); "
                     "L-1 after a year with the company abroad",
    "Canada": "Canada: the employer usually needs an LMIA, or you apply for PR yourself (Express Entry)",
    "Australia": "Australia: the employer must be an approved sponsor (Skills in Demand visa)",
    "New Zealand": "New Zealand: the employer must be accredited and pass a job check (AEWV)",
}
_ANY_PLACE = re.compile(r"\b(global|remote|worldwide|anywhere)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _all_places() -> Places:
    return Places(tuple(all_countries()))


@lru_cache(maxsize=4096)
def _covers(where: str, country: str) -> bool:
    return bool(_ANY_PLACE.search(where)) or country in {c.name for c in _all_places().countries_in(where)}


def _list_covers(details: List[str], country: str) -> bool:
    """Whether a community list's entry ("abhi-jha gist: Berlin, Germany", "relocate.me list: Remote") is for `country`."""
    return any(_covers(d.split(": ", 1)[-1], country) for d in details or [])


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
    "N Irish work permits 2025-2026", "H-1B FY2024: N new, M extended", "positive LMIA 2025Q2-2026Q1: N positions, M in
    software", "on a relocation list"), joined with "; ", or ""."""
    said: List[str] = []
    for ev in _records().get(company or "", []):
        source = ev.get("source")
        if source == "lists":
            if any(_list_covers(d, country) for d in (ev.get("names") or {}).values()):   # the list's entry for this country
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
            elif source == "us":
                said.append(_h1b(ev.get("names") or {}))
            elif source == "ca":
                said.append(_lmia(ev.get("names") or {}))
    return "; ".join(dict.fromkeys(s for s in said if s))


def _span(keys: List[str]) -> str:
    keys = sorted(keys)
    return f"{keys[0]}-{keys[-1]}" if len(keys) > 1 else "".join(keys)


def _h1b(names: Dict[str, Any]) -> str:
    """"H-1B FY2024: 32 new, 233 extended" from {employer name: {fiscal year: [initial, continuing approvals]}}."""
    new = ext = 0
    years: List[str] = []
    for counts in names.values():
        for year, (initial, continuing) in (counts or {}).items():
            new, ext = new + int(initial), ext + int(continuing)
            years.append(year)
    return f"H-1B FY{_span(list(set(years)))}: {new} new, {ext} extended" if new or ext else ""


def _lmia(names: Dict[str, Any]) -> str:
    """"positive LMIA 2025Q2-2026Q1: 12 positions, 3 in software" from {employer name: {quarter: {positions, tech, streams}}}."""
    positions = tech = 0
    quarters: List[str] = []
    for by_quarter in names.values():
        for quarter, e in (by_quarter or {}).items():
            positions, tech = positions + int(e.get("positions") or 0), tech + int(e.get("tech") or 0)
            quarters.append(quarter)
    return f"positive LMIA {_span(list(set(quarters)))}: {positions} positions, {tech} in software" if positions else ""


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
    said = [r for r in (record(company, c.name) for c in countries) if r]
    if kind != "refused":       # the country's own rule unless the posting says no (T141; T143: an offer is still a lottery)
        said += [COUNTRY_RULE[c.name] for c in countries if c.name in COUNTRY_RULE]
    said = list(dict.fromkeys(said))
    return f"{_LABEL[kind]}; {'; '.join(said)}" if said else _LABEL[kind]

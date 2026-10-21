"""Where the person looks for work (T108, T136): their countries and home country from config.json, with built-in packs.

`candidate.countries` (a list or one comma-separated string; default ["India"]) and `candidate.home_country` (default
"India": where the person lives; a job in any other country needs a work visa, T133). India alone keeps the pre-filter's
original rules unchanged (`prefilter.should_evaluate_job`); other countries are matched with the packs below: their names,
cities, the codes boards write (Amazon's "Dubai, ARE", SmartRecruiters' "Berlin, de") and the regions that include them
("Remote - EMEA"). A country without a pack works by its name alone, with a warning at scan start.
"""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from job_hunt.settings import countries_of, home_country_of

# A city that also exists in North America ("London, Ontario", "Dublin, OH", "Cambridge, MA 02139", "Amsterdam, New York")
# counts only when the location has no North American marker; the country's own name always counts.
_NORTH_AMERICA = re.compile(
    r"\b(?i:usa|u\.s\.a?|united states|canada|ontario|quebec|british columbia|alberta|massachusetts|alabama|new hampshire"
    r"|connecticut|ohio|california|virginia|pennsylvania|new york|kentucky|tennessee|texas|michigan|mississippi)\b"
    r"|\b[A-Z]{2}\s*\d{5}\b|,\s*(MA|AL|NH|CT|OH|CA|VA|PA|ON|NY|KY|TN|TX|MI|MS|QC|BC|RI)\b"
    r"|\bUS\b")     # upper case only: "US-CA-Dublin" (the 2026-10-21 fetch)


def _rx(alternatives: str, flags: int = re.IGNORECASE) -> Optional[re.Pattern]:
    """Whole-word alternatives (no letter or digit either side, so "u.k." and "Köln" work)."""
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", flags) if alternatives else None


@dataclass(frozen=True)
class Country:
    name: str
    aliases: Tuple[str, ...] = ()        # how people write it in config.json, lower case
    words: str = ""                      # the country's own names (regex alternatives)
    cities: str = ""                     # cities, states and provinces inside it
    twins: str = ""                      # those of `cities` that also exist in North America
    iso2: str = ""                       # lower-case suffix boards write: "Berlin, de" (upper-case ", DE" is Delaware)
    iso3: str = ""                       # upper case only: "Dubai, ARE", "SGP"
    regions: str = ""                    # region words that include it
    workday_terms: Tuple[str, ...] = ()  # full-text searches for Workday (measured 2026-10-21, T137)
    known: bool = True
    india: bool = False                  # matched with prefilter's India patterns, not the fields above
    _compiled: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def _p(self, key: str) -> Optional[re.Pattern]:
        if key not in self._compiled:
            self._compiled[key] = {
                "words": lambda: _rx(self.words), "cities": lambda: _rx(self.cities),
                "twins": lambda: re.compile(rf"(?:{self.twins})", re.IGNORECASE) if self.twins else None,
                "regions": lambda: _rx(self.regions),
                "iso3": lambda: re.compile(rf"(?<![A-Za-z]){self.iso3}(?![A-Za-z])") if self.iso3 else None,
                "iso2": lambda: re.compile(rf",\s*{self.iso2}\s*$") if self.iso2 else None,
            }[key]()
        return self._compiled[key]

    def names(self, location: str) -> bool:
        """True when the location text names this country, one of its codes, or one of its cities."""
        text = location or ""
        if self.india:
            from job_hunt.prefilter import location_is_india
            return location_is_india(text)
        for key in ("words", "iso3", "iso2"):
            p = self._p(key)
            if p and p.search(text):
                return True
        cities = self._p("cities")
        hits = {m.group(0).lower() for m in cities.finditer(text)} if cities else set()
        if not hits:
            return False
        twins = self._p("twins")
        return not (twins and all(twins.fullmatch(h) for h in hits) and _NORTH_AMERICA.search(text))

    def names_city(self, location: str) -> bool:
        """True when the location names one of this country's cities or states (for candidate.cities)."""
        if self.india:
            from job_hunt.prefilter import _INDIAN_PLACE_PATTERN
            return bool(_INDIAN_PLACE_PATTERN.search(location or ""))
        cities = self._p("cities")
        return bool(cities and cities.search(location or ""))

    def in_region(self, location: str) -> bool:
        regions = self._p("regions")
        return bool(regions and regions.search(location or ""))

    def without_regions(self, location: str) -> str:
        """The location with this country's region words taken out ("EMEA - UK" -> " - UK")."""
        regions = self._p("regions")
        return regions.sub(" ", location or "") if regions else (location or "")


EUROPE = r"europe|emea|eu|eea|european\s+union"

PACKS: Tuple[Country, ...] = (
    Country("India", aliases=("india", "bharat", "in", "ind"), iso3="IND", regions=r"apac|asia|south\s+asia",
            workday_terms=("India",), india=True),
    Country("United Kingdom", aliases=("united kingdom", "uk", "u.k.", "u.k", "great britain", "britain", "england", "gb", "gbr"),
            words=r"united\s+kingdom|u\.k\.?|uk|great\s+britain|britain|(?<!new\s)england|scotland|(?<!new\ssouth\s)wales"
                  r"|northern\s+ireland",
            cities=r"london|manchester|edinburgh|glasgow|cambridge|oxford|bristol|birmingham|leeds|belfast|reading|cardiff"
                   r"|liverpool|sheffield|nottingham|brighton|milton\s+keynes|aberdeen|coventry|leicester|southampton|swindon"
                   r"|guildford|slough|basingstoke|warwick|newcastle\s+upon\s+tyne",
            twins=r"london|cambridge|oxford|bristol|birmingham|reading|manchester|warwick|leicester",
            iso2="gb", iso3="GBR", regions=r"europe|emea|uk\s*&\s*i", workday_terms=("United Kingdom", "UK")),
    Country("Germany", aliases=("germany", "deutschland", "de", "deu"), words=r"germany|deutschland",
            cities=r"berlin|munich|m(?:ü|ue|u)nchen|hamburg|frankfurt|cologne|k(?:ö|oe|o)ln|stuttgart|d(?:ü|ue|u)sseldorf"
                   r"|leipzig|dresden|nuremberg|n(?:ü|ue|u)rnberg|karlsruhe|bonn|hannover|hanover|dortmund|mannheim"
                   r"|heidelberg|walldorf|potsdam|bremen|aachen|wiesbaden|darmstadt|ingolstadt|erlangen|bavaria|bayern"
                   r"|hesse|hessen|baden-w(?:ü|ue|u)rttemberg|north\s+rhine-westphalia|nrw|saxony|brandenburg",
            twins=r"berlin|hamburg|hanover|hannover|dresden|stuttgart|munich|potsdam|bremen|heidelberg",
            iso2="de", iso3="DEU", regions=rf"{EUROPE}|dach", workday_terms=("Germany",)),
    Country("Netherlands", aliases=("netherlands", "the netherlands", "holland", "nederland", "nl", "nld"),
            words=r"netherlands|nederland",
            cities=r"amsterdam|rotterdam|utrecht|eindhoven|the\s+hague|den\s+haag|hague|delft|leiden|groningen|haarlem"
                   r"|amstelveen|hoofddorp|schiphol|nijmegen|tilburg|breda|arnhem|maastricht|zwolle|almere|holland"
                   r"|noord-holland|zuid-holland",
            twins=r"amsterdam|rotterdam|holland|delft",
            iso2="nl", iso3="NLD", regions=rf"{EUROPE}|benelux", workday_terms=("Netherlands",)),
    Country("Ireland", aliases=("ireland", "republic of ireland", "eire", "ie", "irl"), words=r"(?<!northern\s)ireland|eire|éire",
            cities=r"dublin|cork|galway|limerick|waterford|kilkenny|athlone|shannon|sligo|drogheda|dundalk",
            twins=r"dublin|galway|waterford|shannon|limerick",
            iso2="ie", iso3="IRL", regions=rf"{EUROPE}|uk\s*&\s*i", workday_terms=("Ireland",)),
    Country("United Arab Emirates", aliases=("united arab emirates", "uae", "u.a.e.", "u.a.e", "emirates", "dubai", "ae", "are"),
            words=r"united\s+arab\s+emirates|u\.a\.e\.?|uae|emirates",
            cities=r"dubai|abu\s+dhabi|sharjah|ajman|ras\s+al\s+khaimah|fujairah|al\s+ain",
            iso2="ae", iso3="ARE", regions=r"emea|mena|gcc|middle\s+east|gulf",
            workday_terms=("United Arab Emirates", "Dubai")),
    Country("Singapore", aliases=("singapore", "sg", "sgp"), words=r"singapore", iso2="sg", iso3="SGP",
            regions=r"apac|asia|asia\s+pacific|asia-pacific|southeast\s+asia|south\s+east\s+asia|(?-i:SEA)",
            workday_terms=("Singapore",)),
)
_BY_ALIAS = {a: c for c in PACKS for a in (c.name.lower(), *c.aliases)}


def country(written: str) -> Country:
    """The pack for a country name as a person writes it ("UK", "Holland", "uae"); an unknown one gets a pack of its name."""
    key = re.sub(r"\s+", " ", (written or "").strip().lower())
    if key in _BY_ALIAS:
        return _BY_ALIAS[key]
    name = " ".join(written.split())
    return Country(name, aliases=(key,), words=r"\s+".join(map(re.escape, name.split())), workday_terms=(name,), known=False)


@dataclass(frozen=True)
class Places:
    countries: Tuple[Country, ...]
    home: str = "India"

    def india_only(self) -> bool:
        return len(self.countries) == 1 and self.countries[0].india

    def label(self) -> str:
        return ", ".join(c.name for c in self.countries)

    def unknown(self) -> List[str]:
        return [c.name for c in self.countries if not c.known]

    def countries_in(self, location: str) -> List[Country]:
        """Your countries the location names, in your order."""
        return [c for c in self.countries if c.names(location)]

    def region_in(self, location: str) -> Optional[Country]:
        """The first of your countries whose region the location names ("Remote - EMEA" for Germany), else None."""
        return next((c for c in self.countries if c.in_region(location)), None)

    def names_place(self, location: str) -> bool:
        return bool(self.countries_in(location) or self.region_in(location))

    # What the connectors that ask a board for one country send (T137). India alone gives exactly what they sent before:
    # Workday "India", Eightfold and Phenom "India", Oracle HCM the "India" facet, Amazon "IND".
    def search_names(self) -> List[str]:
        return [c.name for c in self.countries]

    def workday_terms(self) -> List[str]:
        terms: List[str] = []
        for c in self.countries:
            terms += [t for t in c.workday_terms if t not in terms]
        return terms

    def amazon_codes(self) -> List[str]:
        return [c.iso3 for c in self.countries if c.iso3]

    def needs_visa(self, location: str) -> bool:
        """True when the job is in one of your countries (or its region) other than home, and not also at home."""
        named = self.countries_in(location)
        if named:
            return all(c.name != self.home for c in named)
        region = self.region_in(location)
        return region is not None and region.name != self.home


INDIA = Places((PACKS[0],), "India")


def places_from_config(config: dict) -> Places:
    found: List[Country] = []
    for written in countries_of(config) or ["India"]:
        c = country(written)
        if c.name not in {f.name for f in found}:
            found.append(c)
    return Places(tuple(found), country(home_country_of(config)).name)


_ACTIVE = INDIA
_LOCAL = threading.local()


def configure_places(source: Union[dict, Places]) -> Places:
    """Make the person's places the ones this process uses (the scan, discover, check-filter); returns them."""
    global _ACTIVE
    _ACTIVE = source if isinstance(source, Places) else places_from_config(source)
    return _ACTIVE


def active_places() -> Places:
    """This thread's places (`using`), else the configured ones."""
    return getattr(_LOCAL, "places", None) or _ACTIVE


@contextmanager
def using(places: Places) -> Iterator[Places]:
    """Within the block, this thread's connectors and filter use `places` (T139: discover checks each company.json entry
    against the places it was accepted for). Each worker thread sets its own."""
    before = getattr(_LOCAL, "places", None)
    _LOCAL.places = places
    try:
        yield places
    finally:
        _LOCAL.places = before


# companies.json entries accepted for countries other than India carry "places": [names] (T139); the others were accepted for India.
def entry_places(entry: Dict[str, Any], home: str = "India") -> Places:
    names = entry.get("places") or []
    return Places(tuple(country(n) for n in names), home) if names else INDIA


def listed_for(entry: Dict[str, Any], places: Places) -> bool:
    """Whether a scan for `places` fetches this entry: an India entry always (big employers hire in many countries), an
    entry accepted for other countries only when it shares one with `places`."""
    names = entry.get("places")
    return not names or bool({country(n).name for n in names} & set(places.search_names()))

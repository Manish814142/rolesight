"""Where the person looks for work (T108, T136, T142): their countries and home country from config.json, for every country.

`candidate.countries` (a list or one comma-separated string; default ["India"]) and `candidate.home_country` (default
"India": where the person lives; a job in any other country needs a work visa, T133). India alone keeps the pre-filter's
original rules unchanged (`prefilter.should_evaluate_job`). Every other country has a pack: hand-made for the United Kingdom,
Germany, the Netherlands, Ireland, the UAE, Singapore, the USA, Canada and Australia (measured search terms, states and
provinces), generated from GeoNames for all the others (job_hunt/data/countries.json, `scripts/build_countries.py`). A pack
knows the country's names, cities, the codes boards write (Amazon's "Dubai, ARE", SmartRecruiters' "Berlin, de", "Austin, TX")
and the regions that include it ("Remote - EMEA"). A location is read part by part ("London; New York"): a part names a country
when it says the country, one of its codes, states or provinces; a city counts only when the part names no other country, so
"London, Ontario" is Canada and "Dublin, OH" the USA (T142, generalising T136's North American guard).
"""
from __future__ import annotations

import importlib.resources
import json
import re
import threading
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Set, Tuple, Union

from job_hunt.settings import countries_of, home_country_of


def _rx(alternatives: str, flags: int = re.IGNORECASE) -> Optional[re.Pattern]:
    """Whole-word alternatives (no letter or digit either side, so "u.k." and "Köln" work)."""
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", flags) if alternatives else None


def _fold(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower().split())


def _alternation(names) -> str:
    return "|".join(r"\s+".join(map(re.escape, n.split())) for n in sorted({n for n in names if n}, key=len, reverse=True))


@dataclass(frozen=True)
class Country:
    name: str
    aliases: Tuple[str, ...] = ()        # how people write it in config.json, lower case
    words: str = ""                      # the country's own names (regex alternatives)
    cities: str = ""                     # cities inside it (a city counts only when its part names no other country)
    iso2: str = ""                       # lower-case suffix boards write: "Berlin, de" (upper-case ", DE" is Delaware)
    iso3: str = ""                       # upper case, after a comma or alone: "Dubai, ARE", "SGP"
    regions: str = ""                    # region words that include it
    workday_terms: Tuple[str, ...] = ()  # full-text searches for Workday (measured 2026-10-21, T137)
    known: bool = True
    india: bool = False                  # matched with prefilter's India patterns, not the fields above
    code: str = ""                       # ISO 3166 alpha-2, upper case ("GB"); "" for a country without a pack
    _compiled: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def _p(self, key: str) -> Optional[re.Pattern]:
        if key not in self._compiled:
            self._compiled[key] = {"words": lambda: _rx(self.words), "cities": lambda: _rx(self.cities),
                                   "regions": lambda: _rx(self.regions)}[key]()
        return self._compiled[key]

    def names(self, location: str) -> bool:
        """True when the location names this country (its name, a code, a state or province) in some part, or one of its
        cities in a part that names no other country."""
        if self.india:
            from job_hunt.prefilter import location_is_india
            return location_is_india(location or "")
        words, cities = self._p("words"), self._p("cities")
        for part in _parts(location):
            named = explicit_countries(part)
            if (self.code and self.code in named) or (not self.code and words and words.search(part)):
                return True
            if not cities:
                continue
            # A city counts unless what qualifies it names another country: its own comma segment and the next one
            # ("London, Ontario", "Aberdeen, MD (Full-Time)") or a code prefix ("US-CA-Dublin"). In a list of cities
            # ("New York, Dubai, London") one item does not qualify the next; a city-state ("Singapore") never does.
            segments = [s.strip() for s in part.split(",")]
            prefix = _prefix_countries(part)
            for i, seg in enumerate(segments):
                if cities.search(seg):
                    around = seg + (", " + segments[i + 1] if i + 1 < len(segments) else "")
                    if not ((explicit_countries(around) | prefix) - {self.code} - CITY_STATES):
                        return True
        return False

    def names_city(self, location: str) -> bool:
        """True when the location names one of this country's cities, states or provinces (for candidate.cities)."""
        if self.india:
            from job_hunt.prefilter import _INDIAN_PLACE_PATTERN
            return bool(_INDIAN_PLACE_PATTERN.search(location or ""))
        cities = self._p("cities")
        return bool((cities and cities.search(location or "")) or _codes_after_comma(location or "") & {self.code})

    def in_region(self, location: str) -> bool:
        regions = self._p("regions")
        return bool(regions and regions.search(location or ""))

    def without_regions(self, location: str) -> str:
        """The location with this country's region words taken out ("EMEA - UK" -> " - UK")."""
        regions = self._p("regions")
        return regions.sub(" ", location or "") if regions else (location or "")


EUROPE = r"europe|emea|eu|eea|european\s+union"

# States and provinces: their names and the codes boards write after a comma ("Austin, TX", "Toronto, ON", "Sydney, NSW").
US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
             "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
             "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
             "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
             "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
             "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
             "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
             "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
             "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"}
CA_PROVINCES = {"ON": "Ontario", "QC": "Quebec", "BC": "British Columbia", "AB": "Alberta", "MB": "Manitoba",
                "SK": "Saskatchewan", "NS": "Nova Scotia", "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
                "PE": "Prince Edward Island", "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut"}
AU_STATES = {"NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland", "WA": "Western Australia",
             "SA": "South Australia", "TAS": "Tasmania", "ACT": "Australian Capital Territory", "NT": "Northern Territory"}
# Names that also mean something else are left to their codes: "Victoria" (Victoria, BC; Seychelles), "Georgia" (the country),
# "Washington" stays (the state and DC are both the USA).
_SUBDIVISION_NAMES = ({"US": [n for c, n in US_STATES.items() if c != "GA"] + ["New England", "Jersey City"],
                       "CA": list(CA_PROVINCES.values()) + ["Québec", "Newfoundland"],
                       "AU": [n for c, n in AU_STATES.items() if c != "VIC"]})
_CODE_OWNERS: Dict[str, Set[str]] = {}
for _iso, _codes in (("US", US_STATES), ("CA", CA_PROVINCES), ("AU", AU_STATES)):
    for _c in _codes:
        _CODE_OWNERS.setdefault(_c, set()).add(_iso)

PACKS: Tuple[Country, ...] = (
    Country("India", aliases=("india", "bharat", "in", "ind"), iso3="IND", regions=r"apac|asia|south\s+asia",
            workday_terms=("India",), india=True, code="IN"),
    Country("United Kingdom", aliases=("united kingdom", "uk", "u.k.", "u.k", "great britain", "britain", "england", "gb", "gbr"),
            words=r"united\s+kingdom|u\.k\.?|uk|great\s+britain|britain|(?<!new\s)england|scotland|(?<!new\ssouth\s)wales"
                  r"|northern\s+ireland",
            cities=r"london|manchester|edinburgh|glasgow|cambridge|oxford|bristol|birmingham|leeds|belfast|reading|cardiff"
                   r"|liverpool|sheffield|nottingham|brighton|milton\s+keynes|aberdeen|coventry|leicester|southampton|swindon"
                   r"|guildford|slough|basingstoke|warwick|newcastle\s+upon\s+tyne",
            iso2="gb", iso3="GBR", regions=r"europe|emea|uk\s*&\s*i", workday_terms=("United Kingdom", "UK"), code="GB"),
    Country("Germany", aliases=("germany", "deutschland", "de", "deu"), words=r"germany|deutschland",
            cities=r"berlin|munich|m(?:ü|ue|u)nchen|hamburg|frankfurt|cologne|k(?:ö|oe|o)ln|stuttgart|d(?:ü|ue|u)sseldorf"
                   r"|leipzig|dresden|nuremberg|n(?:ü|ue|u)rnberg|karlsruhe|bonn|hannover|hanover|dortmund|mannheim"
                   r"|heidelberg|walldorf|potsdam|bremen|aachen|wiesbaden|darmstadt|ingolstadt|erlangen|bavaria|bayern"
                   r"|hesse|hessen|baden-w(?:ü|ue|u)rttemberg|north\s+rhine-westphalia|nrw|saxony|brandenburg",
            iso2="de", iso3="DEU", regions=rf"{EUROPE}|dach", workday_terms=("Germany",), code="DE"),
    Country("Netherlands", aliases=("netherlands", "the netherlands", "holland", "nederland", "nl", "nld"),
            words=r"netherlands|nederland",
            cities=r"amsterdam|rotterdam|utrecht|eindhoven|the\s+hague|den\s+haag|hague|delft|leiden|groningen|haarlem"
                   r"|amstelveen|hoofddorp|schiphol|nijmegen|tilburg|breda|arnhem|maastricht|zwolle|almere|holland"
                   r"|noord-holland|zuid-holland",
            iso2="nl", iso3="NLD", regions=rf"{EUROPE}|benelux", workday_terms=("Netherlands",), code="NL"),
    Country("Ireland", aliases=("ireland", "republic of ireland", "eire", "ie", "irl"), words=r"(?<!northern\s)ireland|eire|éire",
            cities=r"dublin|cork|galway|limerick|waterford|kilkenny|athlone|shannon|sligo|drogheda|dundalk",
            iso2="ie", iso3="IRL", regions=rf"{EUROPE}|uk\s*&\s*i", workday_terms=("Ireland",), code="IE"),
    Country("United Arab Emirates", aliases=("united arab emirates", "uae", "u.a.e.", "u.a.e", "emirates", "dubai", "ae", "are"),
            words=r"united\s+arab\s+emirates|u\.a\.e\.?|uae|emirates",
            cities=r"dubai|abu\s+dhabi|sharjah|ajman|ras\s+al\s+khaimah|fujairah|al\s+ain",
            iso2="ae", iso3="ARE", regions=r"emea|mena|gcc|middle\s+east|gulf",
            workday_terms=("United Arab Emirates", "Dubai"), code="AE"),
    Country("Singapore", aliases=("singapore", "sg", "sgp"), words=r"singapore", iso2="sg", iso3="SGP",
            regions=r"apac|asia|asia\s+pacific|asia-pacific|southeast\s+asia|south\s+east\s+asia|(?-i:SEA)",
            workday_terms=("Singapore",), code="SG"),
    # T142. Cities: the tech hubs and the biggest; a name shared with another country ("Cambridge", "London", "Perth",
    # "Victoria") is left to the state or province code.
    Country("United States", aliases=("united states", "united states of america", "usa", "us", "u.s.", "u.s.a.", "america"),
            words=r"united\s+states(?:\s+of\s+america)?|u\.s\.a?\.?|usa",
            cities=r"new\s+york(?:\s+city)?|nyc|san\s+francisco|sf\s+bay\s+area|bay\s+area|silicon\s+valley|seattle|austin"
                   r"|boston|los\s+angeles|chicago|san\s+jose|mountain\s+view|palo\s+alto|menlo\s+park|sunnyvale|santa\s+clara"
                   r"|cupertino|redmond|bellevue|kirkland|denver|boulder|atlanta|dallas|houston|miami|philadelphia|pittsburgh"
                   r"|raleigh|durham|salt\s+lake\s+city|phoenix|san\s+diego|detroit|minneapolis|nashville|charlotte|irvine"
                   r"|brooklyn|oakland|berkeley|sacramento|san\s+mateo|redwood\s+city|foster\s+city|south\s+san\s+francisco"
                   r"|santa\s+monica|culver\s+city|pasadena|ann\s+arbor|st\.?\s+louis|kansas\s+city|indianapolis|baltimore"
                   r"|orlando|tampa|reston|herndon|mclean|plano|fremont|chandler|scottsdale|columbus|cincinnati|cleveland"
                   r"|milwaukee|new\s+orleans|las\s+vegas|honolulu|washington\s+d\.?c\.?",
            iso2="us", iso3="USA", regions=r"north\s+america|americas|amer", workday_terms=("United States",), code="US"),
    Country("Canada", aliases=("canada", "ca", "can"), words=r"canada",
            cities=r"toronto|montr(?:é|e)al|vancouver|ottawa|calgary|edmonton|winnipeg|mississauga|markham|kitchener"
                   r"|burnaby|brampton|oakville|laval|gatineau|qu(?:é|e)bec\s+city|halifax|regina|saskatoon|fredericton"
                   r"|st\.?\s+john'?s",
            iso2="ca", iso3="CAN", regions=r"north\s+america|americas|amer", workday_terms=("Canada",), code="CA"),
    Country("Australia", aliases=("australia", "au", "aus"), words=r"australia",
            cities=r"sydney|melbourne|brisbane|perth|adelaide|canberra|gold\s+coast|hobart|darwin|geelong|wollongong"
                   r"|parramatta|north\s+sydney",
            iso2="au", iso3="AUS", regions=r"apac|asia\s+pacific|asia-pacific|anz|oceania", workday_terms=("Australia",), code="AU"),
)


@lru_cache(maxsize=1)
def _generated() -> Dict[str, Dict[str, Any]]:
    """job_hunt/data/countries.json (GeoNames, T142): {ISO2: {name, iso3, aliases, cities, regions}}; {} if absent."""
    try:
        text = importlib.resources.files("job_hunt.data").joinpath("countries.json").read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        return {}
    words = data.get("regions") or {}
    out = data.get("countries") or {}
    for c in out.values():
        c["region_words"] = "|".join(words[r] for r in c.get("regions", []) if r in words)
    return out


@lru_cache(maxsize=None)
def _pack(code: str) -> Optional[Country]:
    """The pack of an ISO 3166 alpha-2 code: hand-made when there is one, else generated from GeoNames."""
    for c in PACKS:
        if c.code == code:
            return c
    g = _generated().get(code)
    if not g:
        return None
    names = [g["name"], *g.get("aliases", [])]
    return Country(g["name"], aliases=tuple({_fold(n) for n in names} | {code.lower(), g["iso3"].lower()}),
                   words=_alternation(names), cities=_alternation(g.get("cities", [])), iso2=code.lower(), iso3=g["iso3"],
                   regions=g.get("region_words", ""), workday_terms=(g["name"],), code=code)


def all_countries() -> Tuple[Country, ...]:
    """Every country with a pack: the hand-made ones, then every GeoNames country."""
    codes = [c.code for c in PACKS] + sorted(set(_generated()) - {c.code for c in PACKS})
    return tuple(p for p in (_pack(c) for c in codes) if p)


@lru_cache(maxsize=1)
def _index() -> Tuple[re.Pattern, Dict[str, FrozenSet[str]], Dict[str, str], Dict[str, str], List[Tuple[str, re.Pattern]]]:
    """(names regex, folded name -> countries, ISO3 -> ISO2, ISO2 -> ISO2, hand packs' own word regexes)."""
    by_name: Dict[str, Set[str]] = {}
    for code, g in _generated().items():
        for n in [g["name"], *g.get("aliases", [])]:
            by_name.setdefault(_fold(n), set()).add(code)
    for code, names in _SUBDIVISION_NAMES.items():
        for n in names:
            by_name.setdefault(_fold(n), set()).add(code)
    by_name.setdefault("georgia", set()).update({"US", "GE"})    # the state and the country: both, unless a code says which
    names_rx = re.compile(rf"(?<!\w)(?:{_alternation(by_name)})(?!\w)", re.IGNORECASE)
    iso3 = {g["iso3"]: code for code, g in _generated().items() if g.get("iso3")}
    iso2 = {code: code for code in _generated()}
    hand = [(c.code, c._p("words")) for c in PACKS if c.words]
    return names_rx, {k: frozenset(v) for k, v in by_name.items()}, iso3, iso2, [(c, p) for c, p in hand if p]


# Territories whose name is also their city: in "London, Singapore" Singapore is one more city, not London's country.
CITY_STATES = frozenset({"SG", "HK", "MO", "LU", "MC", "SM", "VA", "GI", "JE", "GG", "IM"})
_ISO3_AT = re.compile(r"(?:^|[,;(]\s*)([A-Z]{3})(?=\s*(?:$|[,;)]|\s[-–]\s))")
_PREFIX = re.compile(r"^\s*([A-Z]{2,3})\s*[-–]")
_ENDS = re.compile(r"\s*(\([^)]*\))?\s*")
_NOT_A_PREFIX = frozenset({"NA", "IT", "AM", "PM"})     # "NA - Remote" is North America (or n/a), not Namibia
_ISO2_SUFFIX = re.compile(r",\s*([a-z]{2})\s*$")
_CODE_AFTER_COMMA = re.compile(r",\s*([A-Z]{2,3})\b")
_ZIP = re.compile(r"\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b")
_US_WORD = re.compile(r"(?<![A-Za-z])US(?![A-Za-z])")       # upper case only: "US-CA-Dublin"
_PART_SPLIT = re.compile(r"\s*(?:;|\||\s/\s|\s+or\s+|\n)\s*", re.IGNORECASE)


def _parts(location: str) -> List[str]:
    """A multi-location string in its parts: "London, UK; New York, NY" -> ["London, UK", "New York, NY"]."""
    return [p for p in _PART_SPLIT.split(location or "") if p.strip()] or [""]


def _has_city_of(code: str, text: str) -> bool:
    if code == "IN":
        from job_hunt.prefilter import LOCATION_INDIA_PATTERN
        return bool(LOCATION_INDIA_PATTERN.search(text))
    pack = _pack(code)
    cities = pack._p("cities") if pack else None
    return bool(cities and cities.search(text))


def _codes_after_comma(part: str) -> Set[str]:
    """Countries an upper-case code after a comma names: a state or province ("Austin, TX", "Toronto, ON", "Sydney, NSW",
    "Dublin, CA 94568") or a country ("Paris, FR"). A code that is both is the country when a city of that country comes
    before it ("Munich, DE" is Germany, "Wilmington, DE" Delaware; "Toronto, CA" Canada, "San Jose, CA" California). WA (the
    US state, Western Australia) and NT (Northwest Territories, Northern Territory) go to Australia only with an Australian city."""
    iso2 = _index()[3]
    found: Set[str] = set()
    tail = _ISO2_SUFFIX.search(part)
    if tail and tail.group(1).upper() in iso2:      # SmartRecruiters' "Magdeburg, SA, de": SA is a German state, not Australia's
        return found
    for m in list(_CODE_AFTER_COMMA.finditer(part)) + list(_ZIP.finditer(part)):
        code, before = m.group(1), part[:m.start()]
        owners = set(_CODE_OWNERS.get(code, set()))
        # A country code ends the location ("Munich, DE"); one in the middle is a region's ("St. Gallen, SG, ch" is a canton).
        last = bool(_ENDS.fullmatch(part[m.end():]))
        if code in iso2 and last and (not owners or _has_city_of(code, before)):
            found.add(code)
            continue
        if len(owners) > 1:
            owners = {"AU"} if _has_city_of("AU", part) else owners - {"AU"}
        found |= owners
    return found


def _prefix_countries(part: str) -> Set[str]:
    """A code at the start that qualifies the rest: "US-CA-Dublin", "GB - London", "IND - Remote"."""
    m = _PREFIX.match(part)
    if not m:
        return set()
    names_rx, by_name, iso3, iso2, _ = _index()
    code = m.group(1)
    if code in _NOT_A_PREFIX:
        return set()
    return {iso3[code]} if code in iso3 else ({code} if code in iso2 else set())


@lru_cache(maxsize=200_000)
def explicit_countries(part: str) -> FrozenSet[str]:
    """The countries one part of a location names outright: a country name or alias, an ISO code where boards put one, a US
    state, Canadian province or Australian state (by name or code). Cities are not here: they are weaker evidence."""
    names_rx, by_name, iso3, iso2, hand = _index()
    found: Set[str] = set()
    for m in names_rx.finditer(part):
        found |= by_name.get(_fold(m.group(0)), frozenset())
    for code, rx in hand:
        if rx.search(part):
            found.add(code)
    found |= {iso3[c] for c in _ISO3_AT.findall(part) if c in iso3}
    found |= {iso2[c.upper()] for c in _ISO2_SUFFIX.findall(part) if c.upper() in iso2}
    found |= {c.code for c in PACKS if c.iso3 and not c.india and _HAND_ISO3[c.code].search(part)}   # "DEU Remote"
    found |= _codes_after_comma(part)
    found |= _prefix_countries(part)                      # "CA-ON-London" is Canada, "GB - London" the UK
    if _US_WORD.search(part):
        found.add("US")
    if found & {"US", "GE"} == {"US", "GE"} and "georgia" in _fold(part):
        found -= {"GE"} if _codes_after_comma(part) & {"US"} or not re.search(r"(?i)tbilisi|batumi|kutaisi", part) else {"US"}
    return frozenset(found)


_BY_ALIAS = {a: c for c in PACKS for a in (c.name.lower(), *c.aliases)}
_HAND_ISO3 = {c.code: re.compile(rf"(?<![A-Za-z]){c.iso3}(?![A-Za-z])") for c in PACKS if c.iso3}


def country(written: str) -> Country:
    """The pack for a country name as a person writes it ("UK", "Holland", "uae", "Brazil", "BR"); a name no pack knows gets
    a pack of its name alone."""
    key = re.sub(r"\s+", " ", (written or "").strip().lower())
    if key in _BY_ALIAS:
        return _BY_ALIAS[key]
    folded = _fold(written)
    for code, g in _generated().items():
        if folded in {_fold(n) for n in [g["name"], *g.get("aliases", []), code, g.get("iso3", "")]}:
            pack = _pack(code)
            if pack:
                return pack
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

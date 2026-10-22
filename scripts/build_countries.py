"""Every country's place pack data, from GeoNames (T142): job_hunt/data/countries.json.

    python scripts/build_countries.py                 # download GeoNames' countryInfo.txt and cities15000.zip, write the file
    python scripts/build_countries.py --offline       # rebuild from the files downloaded last time (data/geonames/)

For each country: its English name and common other names, its ISO 3166 codes (boards write "Dubai, ARE", "Berlin, de"), its
continent, its biggest cities (up to CITIES_PER_COUNTRY, only where this country has the most populous city of that name in the
world: "Valencia" is Venezuela's, so Spain's list leaves it out and only "Valencia, Spain" counts), and the regions job boards
write that include it ("EMEA", "LATAM", "GCC", "DACH"). `job_hunt/places.py` builds a pack from it for any country without a
hand-made pack. Data: GeoNames (https://www.geonames.org), CC BY 4.0; the aliases and regions are this project's.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
COUNTRY_INFO = "https://download.geonames.org/export/dump/countryInfo.txt"
CITIES = "https://download.geonames.org/export/dump/cities15000.zip"
CITIES_PER_COUNTRY = 8

# Other names a board or a person writes (lower case). GeoNames gives one English name per country.
ALIASES: Dict[str, List[str]] = {
    "US": ["united states of america", "usa", "u.s.", "u.s.a.", "u.s.a"], "KR": ["korea", "republic of korea", "korea, republic of"],
    "KP": ["north korea"], "CZ": ["czech republic"], "TR": ["turkey", "türkiye", "turkiye"], "VN": ["viet nam"],
    "RU": ["russian federation"], "CI": ["ivory coast", "côte d'ivoire", "cote d'ivoire"], "CD": ["dr congo",
    "democratic republic of the congo"], "CG": ["republic of the congo"], "MK": ["macedonia"], "SZ": ["swaziland"],
    "MM": ["burma"], "HK": ["hong kong sar"], "MO": ["macao"], "CV": ["cabo verde"], "PS": ["palestinian territories"],
    "AE": ["uae", "u.a.e."], "GB": ["uk", "u.k.", "great britain", "britain", "northern ireland", "england", "scotland", "wales"], "NL": ["the netherlands", "holland"],
    "PH": ["the philippines"], "BR": ["brasil"], "BA": ["bosnia"], "TT": ["trinidad"], "LA": ["lao pdr"], "TW": ["republic of china"],
}

EU = "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
MIDDLE_EAST = "AE BH CY EG IL IQ IR JO KW LB OM PS QA SA SY TR YE".split()
LATAM_EXTRA = "MX BZ CR SV GT HN NI PA CU DO HT JM PR TT BS BB".split()
REGIONS: Dict[str, Tuple[str, List[str]]] = {
    # region key: (the words boards write, its countries; "@XX" means GeoNames continent XX)
    "europe": (r"europe|european", ["@EU"]),
    "eu": (r"eu|european\s+union", EU),
    "eea": (r"eea", EU + ["IS", "LI", "NO"]),
    "emea": (r"emea", ["@EU", "@AF"] + MIDDLE_EAST),
    "middle east": (r"middle\s+east", MIDDLE_EAST),
    "mena": (r"mena", MIDDLE_EAST + ["DZ", "MA", "TN", "LY", "SD"]),
    # Not the bare "gulf" (T146: "Gulf Shores, AL", "Gulf Breeze, FL" are in the USA)
    "gcc": (r"gcc|persian\s+gulf|arabian\s+gulf|gulf\s+region|gulf\s+countries", ["AE", "SA", "QA", "KW", "BH", "OM"]),
    "apac": (r"apac|asia\s+pacific|asia-pacific", ["@AS!ME", "@OC"]),
    "asia": (r"asia", ["@AS"]),
    "sea": (r"southeast\s+asia|south\s+east\s+asia", "BN KH ID LA MY MM PH SG TH VN TL".split()),   # not "SEA": Seattle (T146)
    "south asia": (r"south\s+asia", "AF BD BT IN MV NP PK LK".split()),
    "latam": (r"latam|latin\s+america", ["@SA"] + LATAM_EXTRA),
    "south america": (r"south\s+america", ["@SA"]),
    "north america": (r"north\s+america", ["US", "CA", "MX"]),
    "americas": (r"americas", ["@NA", "@SA"]),
    "africa": (r"africa", ["@AF"]),
    "nordics": (r"nordics?|scandinavia", "DK FI IS NO SE".split()),
    "dach": (r"dach", ["DE", "AT", "CH"]),
    "benelux": (r"benelux", ["BE", "NL", "LU"]),
    "cee": (r"cee|central\s+and\s+eastern\s+europe|eastern\s+europe", "PL CZ SK HU RO BG HR SI EE LV LT RS BA ME MK AL MD UA".split()),
    "anz": (r"anz|oceania", ["AU", "NZ"]),
    "uk&i": (r"uk\s*&\s*i|uki", ["GB", "IE"]),
}


def _fold(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()


def parse_country_info(text: str) -> Dict[str, Dict[str, Any]]:
    """GeoNames countryInfo.txt -> {ISO2: {name, iso3, continent, capital, population}}."""
    out: Dict[str, Dict[str, Any]] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) < 9 or len(f[0]) != 2:
            continue
        out[f[0]] = {"name": f[4], "iso3": f[1], "capital": f[5], "population": int(f[7] or 0), "continent": f[8]}
    return out


def parse_cities(text: str) -> List[Tuple[str, str, str, int]]:
    """GeoNames cities15000.txt -> [(name, ascii name, ISO2, population)]."""
    rows = []
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) > 14 and f[8]:
            rows.append((f[1], f[2], f[8], int(f[14] or 0)))
    return rows


def regions_of(iso2: str, continent: str) -> List[str]:
    found = []
    for key, (_, members) in REGIONS.items():
        for m in members:
            if m == iso2 or m == f"@{continent}" or (m == "@AS!ME" and continent == "AS" and iso2 not in MIDDLE_EAST):
                found.append(key)
                break
    return found


def build(country_info: str, cities_text: str) -> Dict[str, Any]:
    countries = parse_country_info(country_info)
    cities = parse_cities(cities_text)
    biggest: Dict[str, Tuple[int, str]] = {}            # folded city name -> (population, ISO2) of its most populous instance
    for name, ascii_name, iso2, pop in cities:
        for n in {_fold(name), _fold(ascii_name)}:
            if n and (n not in biggest or pop > biggest[n][0]):
                biggest[n] = (pop, iso2)
    country_words = {_fold(c["name"]) for c in countries.values()} | {a for v in ALIASES.values() for a in v}
    out: Dict[str, Any] = {}
    for iso2, c in sorted(countries.items()):
        own = sorted((r for r in cities if r[2] == iso2), key=lambda r: -r[3])
        names: List[str] = []
        for name, ascii_name, _, _ in own:
            for n in dict.fromkeys([name, ascii_name]):
                f = _fold(n)
                if len(f) > 2 and biggest.get(f, (0, ""))[1] == iso2 and f not in country_words and n not in names:
                    names.append(n)
            if len({_fold(n) for n in names}) >= CITIES_PER_COUNTRY:
                break
        out[iso2] = {"name": c["name"], "iso3": c["iso3"], "aliases": ALIASES.get(iso2, []), "continent": c["continent"],
                     "cities": names, "regions": regions_of(iso2, c["continent"])}
        followers = _followers(names, iso2, cities)
        if followers:
            out[iso2]["not_followed_by"] = followers
    return out


def _followers(names: List[str], iso2: str, cities: List[Tuple[str, str, str, int]]) -> Dict[str, List[str]]:
    """For each kept city, the next words of other countries' cities that begin with its name (T146: "Porto Alegre" and
    "Porto Velho" are Brazil's, so "Porto" counts for Portugal only when no such word follows)."""
    out: Dict[str, List[str]] = {}
    for n in names:
        f = _fold(n)
        nxt = sorted({rest.split()[0] for name, ascii_name, other, _ in cities if other != iso2
                      for g in {_fold(name), _fold(ascii_name)} if g.startswith(f + " ")
                      for rest in [g[len(f) + 1:]] if rest.split()})
        if nxt:
            out[n] = nxt
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "job_hunt" / "data" / "countries.json"))
    ap.add_argument("--sources", default=str(ROOT / "data" / "geonames"), help="where the downloads go (git-ignored)")
    ap.add_argument("--offline", action="store_true", help="use the files downloaded last time")
    args = ap.parse_args(argv)
    src = Path(args.sources)
    if not args.offline:
        import requests
        src.mkdir(parents=True, exist_ok=True)
        (src / "countryInfo.txt").write_bytes(requests.get(COUNTRY_INFO, timeout=120).content)
        (src / "cities15000.zip").write_bytes(requests.get(CITIES, timeout=300).content)
    elif not (src / "countryInfo.txt").exists():
        sys.exit(f"build_countries: nothing downloaded in {src} yet; run once without --offline")
    with zipfile.ZipFile(io.BytesIO((src / "cities15000.zip").read_bytes())) as z:
        cities_text = z.read("cities15000.txt").decode("utf-8")
    countries = build((src / "countryInfo.txt").read_text(encoding="utf-8"), cities_text)
    data = {"about": "Every country's names, ISO codes, main cities and regions, for job_hunt/places.py (T142). Rebuild: "
                     "python scripts/build_countries.py",
            "source": {"data": "GeoNames countryInfo.txt and cities15000 (https://www.geonames.org)", "licence": "CC BY 4.0",
                       "built": dt.date.today().isoformat(), "cities_per_country": CITIES_PER_COUNTRY,
                       "aliases_and_regions": "this project's (scripts/build_countries.py)"},
            "regions": {k: v[0] for k, v in REGIONS.items()},
            "countries": countries}
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(countries)} countries, {sum(len(c['cities']) for c in countries.values())} city names -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

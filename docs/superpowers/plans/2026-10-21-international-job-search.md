# International job search (T108) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a person in India can search jobs in the countries they choose (first: United Kingdom, Germany, Netherlands,
Ireland, United Arab Emirates, Singapore), see per job whether a visa is offered, refused or unstated, and get companies
that hire there, while Manish's India setup behaves exactly as today.

**Architecture:** one new module, `job_hunt/places.py`, turns `config.json` into a `Places` value (the person's countries,
their home country, built-in place packs). The pre-filter, the five connectors that ask a board for one country, the
rubric's location rule, `discover`'s gate and the scan read it. A second module, `job_hunt/visa.py`, gives each job outside
the home country a visa note from the posting's own words and the company records of T133. An India-only `Places` takes
today's code paths unchanged.

**Tech Stack:** Python 3.11+, requests, pytest (no network in tests), the existing adapters.

**Spec:** the T108 entry of `docs/tasks.md` (design 2026-10-14, the T133 note of 2026-10-21) and these answers from
Manish: build it (2026-10-21, "work on all dependent tasks to make the full international job hunt possible"); the people
are in India and relocate, so the company must sponsor the visa; first countries are the six measured in T133; Japan is
dropped where postings are in Japanese.

## Global Constraints

- **India unchanged:** with no `candidate.countries` (or `["India"]`), the pre-filter decides the same on the saved fetches
  (2026-10-13, 39,985 jobs; 2026-10-21, 71,121 jobs: 0 differences), every connector sends the same requests, the rubric
  text and its id (`82e017b4`) are the same, the CSV columns and the scan log's filter and funnel lines are the same, and
  `companies.json` entries without `places` are scanned as before.
- **Config (my call, from the T108 design):** `candidate.countries` (a list or one comma-separated string; default
  `["India"]`), `candidate.home_country` (default `"India"`: where the person lives; a job in another country needs a visa),
  `candidate.cities` unchanged (any country's cities). No remote-policy setting: remote rules stay today's (a remote job
  passes when it names one of your places or no place at all, or says worldwide/anywhere).
- **Tests make no network calls.** Measurements that need the network are scripts, run by hand, and recorded.
- **Drafts only;** nothing applies anywhere.
- One task at a time on the board (claim, implement, review); each part below is its own board ID.

## Review Focus

1. A city that also exists in North America ("London, Ontario", "Dublin, OH", "Cambridge, MA", "Birmingham, AL") must
   not count as the UK or Ireland. Test in Task 1.
2. A country spelled the way people write it ("UK", "U.K.", "Britain", "UAE", "Holland", "Deutschland", lower case)
   must resolve to its pack; an unknown country ("Canada") must work by its name, with one warning, and never crash.
   Tests in Task 1.
3. Board-style locations with codes only: Amazon's "SGP", "Dubai, ARE", "Dublin, IRL"; SmartRecruiters' "Berlin, de"
   (but upper-case ", DE" is Delaware). Tests in Task 1.
4. A `rubric.md` whose rule 1 the person rewrote: kept as written, with a scan-log warning, not silently replaced.
   Test in Task 3.
5. Several search terms per country on a rate-limited board (Accenture answered HTTP 429 to 3 of 5 searches,
   2026-10-21): the 600 s board budget is shared by all terms, and a failed term keeps what the others returned.
   Test in Task 2.

---

### Task 1 (board T136): places in config, the pre-filter and `check-filter`

**Files:** Create `job_hunt/places.py`, `tests/test_places.py`. Modify `job_hunt/prefilter.py` (`should_evaluate_job`),
`job_hunt/settings.py`, `job_hunt/scanner.py` (configure at scan start; filter call; the two log lines and the funnel
label), `job_hunt/onboarding.py` (`check-filter --countries`), `scripts/measure_visa_wording.py` (use the packs).

**Interfaces (produced):**
- `Country` (frozen dataclass): `name`, `aliases: tuple[str, ...]`, `pattern: re.Pattern` (country words, cities, states),
  `twins: re.Pattern | None` (its cities that also exist in North America), `iso2: str` (lower-case board suffix, e.g. `gb`),
  `iso3: str` (upper-case, e.g. `GBR`), `regions: tuple[str, ...]`, `workday_terms: tuple[str, ...]`, `known: bool`.
- `Places` (frozen dataclass): `countries: tuple[Country, ...]`, `home: str`; methods `india_only() -> bool`,
  `label() -> str` ("India"; "United Kingdom, Germany"), `country_in(location) -> Country | None`,
  `region_in(location) -> str`, `names_place(location) -> bool` (a country or one of its regions),
  `needs_visa(location) -> bool`, `unknown() -> list[str]`.
- `places_from_config(config: dict) -> Places`; `configure_places(config_or_places) -> Places` (module-level active);
  `active_places() -> Places` (India by default); `INDIA: Places`.
- `prefilter.should_evaluate_job(job, cities=None, places=None)`: `places=None` means `active_places()`; India-only goes
  through today's code, line for line.

**Packs (measured on the 2026-10-21 fetch and the 2026-10-21 probes):** UK (`united kingdom|uk|u.k.|england|scotland|wales|
great britain|britain|northern ireland` + main cities; twins London, Cambridge, Birmingham, Manchester, Reading, Bristol;
`gb`/`GBR`; regions europe, emea, uk&i; Workday terms "United Kingdom", "UK"), Germany (`germany|deutschland` + cities incl.
München/Muenchen, Köln; twins Berlin, Hanover, Hamburg; `de`/`DEU`; europe, emea, eu, eea, european union, dach;
"Germany"), Netherlands (`netherlands|nederland|holland` + cities; twins Amsterdam, Rotterdam; `nl`/`NLD`; europe, emea, eu,
eea, european union, benelux; "Netherlands"), Ireland (`ireland` not after "northern" + Dublin, Cork, Galway, Limerick;
twins Dublin; `ie`/`IRL`; europe, emea, eu, eea, uk&i; "Ireland"), UAE (`united arab emirates|uae|u.a.e.|emirates` + Dubai,
Abu Dhabi, Sharjah; `ae`/`ARE`; emea, mena, gcc, middle east; "United Arab Emirates", "Dubai"), Singapore (`singapore`;
`sg`/`SGP`; apac, asia, asia pacific, sea, southeast asia; "Singapore"), India (today's patterns; `IND`; apac, asia;
"India"). An unknown name gets a pack of its own words, no codes, no twins, Workday term = the name.

**Rule for a non-India `Places` (my call, mirroring today's India rule):** title first (unchanged); a chosen city passes;
a location that names one of your countries passes (with cities chosen, an on-site job in another city of that country is
rejected, as for India); a region word of one of your countries passes; worldwide/anywhere/global passes; a remote job that
names no place passes; anything else is rejected with "Location '…' is not in your places (…)".

- [ ] Tests first (`tests/test_places.py`): packs resolve aliases; `country_in` for "London, UK" → UK, "London, Ontario" →
  None, "Dublin, OH" → None, "Remote - USA; London, United Kingdom" → UK, "SGP" → Singapore, "Dubai, ARE" → UAE, "Berlin, de"
  → Germany, "Wilmington, DE" → None; `should_evaluate_job` with a UAE+Singapore config: "Backend Engineer" in "Dubai, United
  Arab Emirates" KEPT, in "Bengaluru, India" REJECTED, "Remote - EMEA" KEPT, "Remote - US" REJECTED, "Remote" KEPT,
  "Worldwide" KEPT; India-only `Places` and `places=None` give byte-identical reasons to today on a fixed list of 40
  locations; "Canada" config → unknown warning, "Toronto, Canada" KEPT.
- [ ] Implement; run `pytest tests/test_places.py tests/test_prefilter*.py`.
- [ ] Wire the scanner and `check-filter --countries "United Kingdom, Germany"`.
- [ ] **Measure:** on both saved fetches, the India-only config against today's call: 0 differences; a UAE config:
  list the kept jobs and the rejected India jobs, read by hand.
- [ ] Commit `T136: …`, CHANGELOG, Review queue.

### Task 2 (board T137): the five connectors search your places

**Files:** Modify `job_hunt/adapters/workday.py`, `eightfold.py`, `phenom.py`, `oracle_hcm.py`, `amazon.py`,
`adapters/__init__.py`; tests in the existing adapter test files.

**Interfaces (consumed):** `active_places()`; `Country.workday_terms`, `Country.name`, `Country.iso3`.

**Decisions (measured 2026-10-21 by probes):** Workday runs one search per term (UK: "United Kingdom" 37 / "UK" 60 hits
at ABB; UAE: "United Arab Emirates" 10 / "Dubai" 12 at Salesforce), all terms sharing `seen_paths`, the `MAX_JOBS` cap per
term and one 600 s budget. Eightfold: one search per country name (Qualcomm: UK 20, Singapore 29). Phenom: one search
with the list of names (BCG: UK + Germany 189 = 109 + 85 − 5 shared). Oracle HCM: one facet per country; a country with no
facet among the site's facets (they list only the 10 biggest locations: Akamai has Germany, not the UK) reads the site
newest first without a facet, stopped by the posted-date window — for a non-India `Places` only; India keeps "no India facet
→ nothing". Amazon: one search per `iso3` (GBR 759, DEU 663, NLD 34, IRL 227, ARE 64, SGP 134); an unknown country is
skipped with a debug line.

- [ ] Tests first: with India active, each connector's request payloads/params equal today's (recorded stubs); with
  UK+Singapore active, Workday sends "United Kingdom", "UK", "Singapore" and dedupes a job both return; a 429 on one term
  keeps the other terms' jobs and marks the fetch incomplete; the budget is shared; Amazon asks GBR and SGP; Phenom sends
  both names in one list; Oracle uses the Germany facet when listed and the windowed full read when not.
- [ ] Implement; adapter tests pass.
- [ ] **Measure:** `scan`'s fetch for a UK+Singapore config on 5 boards of each connector: jobs per country, time.
- [ ] Commit `T137: …`.

### Task 3 (board T138): scoring knows your places; a Visa column

**Files:** Create `job_hunt/visa.py`, `tests/test_visa.py`. Modify `job_hunt/llm_utils.py` (`configure_rubric`,
structured instructions), `job_hunt/exporter.py` (`OPTIONAL_COLUMNS` "Visa", `job_from_db_row` passes the description),
`job_hunt/main.py`/`onboarding.py` (export configures places), `scripts/measure_visa_wording.py` (import the classifier).

**Interfaces:** `visa.wording(text) -> tuple[str, str]` ("offered" | "refused" | "mentioned" | "silent", sentence; the
T133 classifier moved); `visa.record(company, country) -> str` (from `job_hunt/data/visa_sponsors.json`: "UK licensed
sponsor", "Dutch recognised sponsor", "N Irish permits 2025–26", "on a relocation list", or ""); `visa.note(company,
location, description, places) -> str` ("" when `places.needs_visa(location)` is False). `llm_utils.rubric_for_places(text,
places) -> tuple[str, str | None]` (text, warning).

**Rule 1 for a non-India `Places` (my wording):** "If the job requires on-site or hybrid presence outside {places}, cap
score at <= 30. The candidate lives in {home} and needs the employer to sponsor a work visa for any role outside {home}: if
the posting says it cannot sponsor a visa, or requires citizenship, permanent residence or an existing right to work in that
country, cap score at <= 30. A posting that says nothing about visas is not capped for that. (Roles in {places}, whether
on-site, hybrid or remote, and remote roles open to candidates there, are eligible for higher scores.)" Rule 5's
"Location fits (India or Remote)." becomes "Location fits ({places} or Remote).". Only the built-in lines are replaced
(they survive `init --resume`, whose draft keeps rule 1); a rewritten rule 1 is kept, with a warning.

**Visa note (my wording, measured precision of the classifier in T133: refused 12/12, offered 10/12):** "Posting: no visa
sponsorship" / "Posting: offers visa sponsorship" / "Posting: unclear" / "Not stated" — followed by "; " and the company
record when there is one ("Not stated; UK licensed sponsor"). A posting's own refusal is shown first: 17 of 44 refusing UK
companies are licensed (T133).

- [ ] Tests first: India-only → the rubric text and id unchanged; UK+Germany → rule 1 and rule 5 lines replaced, the rest
  byte-identical; a rewritten rule 1 → kept + warning; `note` for a London job with a refusal / an offer / silence at Stripe
  (record) / silence at an unknown company; an India job with a UK+India config → ""; the CSV gets "Visa" only when a row
  has one; `export` from the database fills it.
- [ ] Implement; tests pass; `pytest` whole suite.
- [ ] Commit `T138: …`.

### Task 4 (board T139): `discover` checks your places; companies that hire abroad

**Files:** Modify `job_hunt/discovery.py` (`--places`, the gate, `place_jobs` column, entry `places`, the Workday light
check's terms, recheck per entry), `job_hunt/scanner.py` (skip an entry whose `places` share none of yours),
`companies.json` + `job_hunt/data/companies.json` (the abroad employers), `tests/test_discovery.py`.

**Decisions (my call):** the gate is "≥ 1 job in the places" — `--places` if given, else `config.json`'s countries, else
India; the report's `india_jobs` column becomes `place_jobs` (the verdict for India stays "no India jobs"); an entry accepted
for a non-India `Places` carries `"places": [names]`; the recheck checks each entry against its own `places` (absent = India);
the scan fetches an entry with `places` only when they share a country with yours, so an India-only scan fetches exactly
today's 1,589.

- [ ] Tests first: gate with UK places accepts a board with London jobs and no India job; India unchanged ("no India
  jobs"); `places` written on the entry; recheck uses the entry's places; the scan skips a UK-only entry for India and
  fetches it for UK.
- [ ] Implement; tests pass.
- [ ] **Run:** `autopilot discover --add-file <T135's seeds> --places "United Kingdom, Germany, Netherlands, Ireland, United
  Arab Emirates, Singapore" --merge companies.json --no-recheck --report …` → read the accepted rows by hand, copy the list.
- [ ] Commit `T139: …`.

### Task 5 (board T140): `init --countries`, the guide, and the end-to-end check

**Files:** Modify `job_hunt/onboarding.py` (`init --countries`), `config.example.json` + `job_hunt/data/config.example.json`
(`countries`, `home_country`), `docs/00-user-guide.md` (a section "Looking for jobs outside India"), `docs/07-config-and-scoring.md`,
`docs/10-limitations-and-future-work.md`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/tasks.md` (T108 to the Done log
after review).

- [ ] Test first: `init --countries "Singapore"` writes `candidate.countries == ["Singapore"]`; both example configs equal
  and valid.
- [ ] **End-to-end (T108's Done when):** a fresh folder, `rolesight init --yes --countries Singapore`, a `companies.json` of 5
  boards including a Workday and an Eightfold board, `rolesight scan` with Manish's Gemini key from the environment (never
  written to a file): Singapore jobs fetched (the Workday/Eightfold ones by a Singapore search), scored, and the CSV has a
  Visa column.
- [ ] Commit `T140: …`; T108's row moves to review with T136–T140.

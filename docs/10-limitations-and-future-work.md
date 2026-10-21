# 10 — Limitations and future work

What RoleSight does **not** do today, where in the code each limit lives, and ideas for extending it. Written so
that someone picking the project up knows what is fixed to one setup before they rely on it, and where to start
changing it. Status as of 2026-10-14; the live list of work is the task board, [tasks.md](tasks.md).

RoleSight was built for one person: a backend engineer with about 3 years of experience, looking for jobs in India
or remote. Much of that is now a setting (the title words, the profile, the rubric: `rolesight init --resume` drafts
them from anyone's resume). What follows is what is still fixed.

## 1. What is fixed today

### Location: India by default; six other countries built in (T108, 2026-10-21)

**Update 2026-10-21 (T136–T140): this is a setting now.** `candidate.countries` (e.g. `["United Kingdom", "Germany"]`) and
`candidate.home_country` change all six places below: the filter (country packs in `job_hunt/places.py`), the five
connectors' searches, rule 1 (with the visa rule), `discover --places`, the summary line, and the list (27 companies that
hire abroad, listed for those countries). See the [user guide](00-user-guide.md#looking-for-jobs-outside-india). What is
still limited: since T142 every country has a pack, but a GeoNames one knows only the country's 8 biggest cities (a job that
names only a smaller city needs the country in its location, or the city in `candidate.cities`), and a name some other country's
bigger city also has is left to its country word ("Valencia"); postings in
another language do not match the English title words; Germany, the UAE and Singapore have no sponsor register (the Visa note gives their rule instead, T141); a scan for
several countries makes more requests. The rest of this section describes the state before T136, kept for the record.

Before T136, India was built into six places:

| Where | What it does | File |
|---|---|---|
| The location filter | Only Indian places (India, its states and union territories, about 140 place names in all, `IND`) and remote jobs open to India pass; other regions are rejected | `job_hunt/prefilter.py` (`LOCATION_INDIA_*`, `LOCATION_EXCLUDE_PATTERN`) |
| Four job-board adapters | They **ask the board for India jobs only**, so other countries' jobs are never fetched from these boards | `adapters/workday.py` (`SEARCH_TEXT`), `eightfold.py` (`SEARCH_LOCATION`), `phenom.py` (`SEARCH_COUNTRY`), `oracle_hcm.py` (the India facet) |
| The scoring rubric, rule 1 | Caps a job that needs on-site work outside India at 30 | `job_hunt/llm_utils.py` (`SCORING_RUBRIC`) |
| `discover` | Accepts a company only when it has at least one job in India | `job_hunt/discovery.py` |
| The scan's summary line | Counts the jobs "in India" | `job_hunt/scanner.py` |
| The company list | 1,589 boards, each checked to have a job in India | `companies.json` |

A partial workaround exists but is not enough: a city listed in `candidate.cities` counts even when the India lists do
not know it, so `"cities": ["Dubai"]` lets "Dubai, United Arab Emirates" through the filter (checked with
`rolesight check-filter`). But remote jobs open to India still pass, the four adapters above still fetch India only, and
rule 1 still caps on-site work outside India. The other adapters (Greenhouse, Lever, Ashby, SmartRecruiters, …)
already return every location: the saved fetch of 2026-10-13 holds 41 jobs in Dubai / UAE, 629 in Singapore and 2,268
in the UK, Germany, the Netherlands, France, Ireland, Spain and Poland. The filter rejects them unless the job also
names an Indian place (5 of the 41 Dubai jobs do, e.g. "Bangalore, Dubai, Geneva, …").

**How it was extended (T136–T140):** as the T108 design said, with `candidate.countries` instead of `candidate.locations`
and no remote-policy setting (remote rules are India's: a remote job passes when it names one of your places or none).
More countries: add a `Country` pack to `job_hunt/places.py` (names, cities, the cities that also exist in North America,
the codes boards write, regions, Workday search terms measured on real tenants) and a test in `tests/test_places.py`.

### Which companies can be scanned

- Only companies whose careers page runs on an ATS with a **public JSON API**: Greenhouse, Lever, Ashby,
  SmartRecruiters, Workday, Recruitee, Personio, Workable, Oracle HCM, Eightfold, Phenom, and Amazon's own.
- **Not reachable:** custom careers sites (Google, Flipkart, Swiggy, …) and platforms without a public API
  (Darwinbox, which also blocks scripts with Cloudflare Turnstile; Zoho Recruit; Freshteam). On 2026-10-06, 52% of
  458 careers pages checked were JavaScript-only or used an unidentified system.
- **Not scraped on purpose:** LinkedIn and Naukri (cost and the risk of an account ban).
- The list must be kept up by hand: `rolesight discover --add` checks and adds companies, and `discover --recheck`
  (or `scripts/monthly_recheck.sh`) finds dead boards.

### Scoring

- **Gemini is the only provider used for real.** `anthropic` and `claude_cli` are still in the code but have never
  scored a real job (only stubbed tests run them).
- **Free-tier limits:** 500 calls per model per day and 15 per minute, so a job takes about 6 seconds; the first full
  scan of 224 boards took 48.5 minutes. Later scans score only new jobs.
- **Scores vary between runs**, by about 3 points on average; an ambiguous posting can land on either side of
  `min_score`, and temperature 0 does not remove that.
- **The built-in rubric was written and measured for one person.** A rubric drafted by `init --resume` was measured
  once, on that same person: on 82 labelled jobs it ranked a little worse than the hand-tuned one (AUC 0.931 against
  0.955 and 0.953 the same day).
- **The test labels are an AI's.** All but one of the 82 labelled jobs were labelled by Claude, not confirmed by the
  person (task T59), so the accuracy figures above are indicative.
- **A stored score is final.** After a rubric change, old scores stay; a scan can re-score only a job it fetches again,
  inside the posted-date window and passing today's filter (on 2026-10-14, 3 of 145 old rows qualified).

### The filter's word rules

- **A resume cannot say what you do not want.** `init --resume` drafts from the resume, so a Java developer who
  wants only Node.js roles must add `java` to `exclude` by hand.
- **Place names have no country context:** "Kochi, Japan" counts as India (the list knows Kochi, Kerala).
- `SDE10` and higher written without a space do not match the default include words (`sde1`–`sde9` do).

### Running it

- **Not scheduled by default.** Scans run by hand; `autopilot schedule on` turns a daily scan on (systemd user timer on
  Linux, else cron, which also covers macOS) and `schedule off` turns it off. The cron path was written for macOS but has
  not been run on a Mac. There is no ready-made scheduler for Windows.
- **Tested on Linux only.** CI runs on Ubuntu with Python 3.11, 3.12 and 3.13.
- **Telegram alerts are unverified:** the last send attempts (2026-10-03) failed with HTTP 404. The CSV is the main
  output.
- **No web interface:** everything is files and commands. A web UI was designed and parked as too much work for its
  benefit (`docs/superpowers/specs/2026-10-10-web-ui-design.md`).
- **Nothing but the code is backed up:** `data/jobs.db` (the seen-job memory), your resume and your keys stay on
  your machine only.
- The company-size badge comes from an old LinkedIn cache and is shown, never used to filter.

## 2. Future goals

Ideas, not started. The first ones help a job seeker most; the size is a rough estimate.

| Idea | What it would do | Size |
|---|---|---|
| Any country (T108) | Search Dubai, Singapore, Europe…: the design above | about a day |
| Score any job you find | `rolesight score <URL or pasted text>`: a job seen on LinkedIn, Naukri or a referral, scored with the same rubric and kept in the tracker. Covers the boards RoleSight cannot reach, without scraping | small |
| A short daily list | "Today: 5 to apply" instead of a 100-row CSV, plus a desktop notification when the scan finishes | small |
| Learn from your decisions | `mark N skip "reason"` next to `applied`: skip reasons point at filter and rubric fixes, and your own marks become the test labels | small to medium |
| Referrals | Import your LinkedIn connections export (a CSV LinkedIn lets you download) and show who you know at each company | small to medium |
| Follow-ups and outcomes | A reminder when an application gets no answer; a weekly count of applied → interview → offer by score band, the real test of the scorer | medium |
| Interview prep | For a job you reach the interview with: likely topics, the gaps in your resume, questions to ask (drafts only) | small |
| Region company lists | Starter `companies.json` lists for Europe, Singapore, the Gulf, built with `discover` | medium |
| More job boards | Adapters for other systems with public APIs (not yet checked: Keka, Zoho Recruit, …) | per board |
| Re-score after a rubric change | A command that finds the stored scores a scan can still re-score, and resets only those | small |
| Scheduling on Windows (and launchd on macOS) | Task Scheduler (and launchd) next to the systemd timer and cron; today `schedule on` on Windows only explains the steps | small |

## 3. Picking one up

- The [task board](tasks.md) is how work is claimed, built and verified (its Working loop); [CONTRIBUTING.md](../CONTRIBUTING.md)
  has the setup and the gates (`pytest` with an 85% coverage gate, `ruff`, `mypy`).
- Two rules that are never relaxed: **drafts only** (RoleSight never applies or submits anything), and **tests make no
  network calls**.
- When you change what reaches Gemini or how it scores, prove the default setup does not change, the way the title
  filter was moved into `config.json` (T103: the same decision on all 39,985 jobs of a saved fetch), and measure the
  new setup on labelled jobs.

# 07 — Config & scoring

## `config.json` reference

The file is gitignored; start from `config.example.json`. Any key can be left out, and
the default shown applies. A key is read only in the place the tables below put it: `scoring_mode` and `max_jobs_to_score_per_run`
belong at the top level, not under `candidate` (an earlier version of this page listed them under `candidate`, where the code never
looks, so a value put there was ignored; T80). The step-by-step version of this page is the [user guide](00-user-guide.md).

### Top level

| Key | Default | Used for |
|---|---|---|
| `llm_provider` | `gemini` | Drafting, and scoring when no Gemini key is set ([02](02-providers.md)) |
| `gemini_api_key` | — | Scoring. Usually set as `GEMINI_API_KEY` in `.env` instead |
| `gemini_model` | `gemini-3.5-flash-lite` | Primary scoring model; the fallback is `gemini-3.1-flash-lite` |
| `gemini_scoring_mode` | `single` | `batch` scores several jobs per call. Faster, but measured to inflate scores ([02](02-providers.md#batch-mode-opt-in-not-recommended)) |
| `gemini_batch_size` | `10` | Jobs per call in batch mode |
| `gemini_temperature` | `0.1` | Sampling temperature of every Gemini scoring call: single, batch and structured (T60 measured that 0 does not remove the score noise; T69 a made the last two read it) |
| `fetch_workers` | `8` | Companies fetched in parallel; also used for description fetching |
| `scoring_mode` | `holistic` | `holistic`: one score from the prompt with the rubric. `structured`: the model reports sub-scores and facts, code applies the caps and computes the score; the CSV gets Stack/Role/Seniority/Location fit, Min years and Capped by columns (T41). Not the default: calibration was worse on the labelled set (see CHANGELOG 2026-10-06) |
| `max_jobs_to_score_per_run` | 0 | Score at most this many jobs per run, newest first; the rest stay `discovered` for the next scan. `0` = no cap, the default since T118 (Gemini's per-model daily limits are the limit, and the second model takes over when the first has used its day) |
| `open_matches_scope` | `this_run` | What `output/open_matches.csv` holds. `this_run`: the jobs the scan that just ran scored (T124). `all_open`: every scored job ≥ `min_score` that is not marked and not closed, old ones included (the rolling list of T39). Any other value stops the scan before it fetches |
| `telegram.token`, `telegram.chat_id` | — | Optional alerts ([05](05-outputs-and-notifications.md#telegram-optional)) |
| `anthropic_api_key`, `anthropic_model` | — | `llm_provider: anthropic` |
| `claude_cli_model` | Claude's default | `llm_provider: claude_cli` |

### `candidate`

| Key | Default | Used for |
|---|---|---|
| `name` | "the candidate" | Prompt context |
| `resume_path` | `resume/YOUR_RESUME.md` | Resume file sent **in full** with every scoring call |
| `profile` | — | One-line summary in every scoring prompt ("3 YOE backend, Node.js…") |
| `seeking` | — | What the candidate wants (roles, cities, remote), in every prompt |
| `not_suitable` | — | What to score low, in every prompt |
| `min_score` | `70` (code default and example config; set once, here, T05) | Score that counts as a match: "Worth Applying", Telegram alerts, the digest |
| `top_n` | `5` | How many matches the digest and the log summary show |
| `max_posted_age_days` | `7` | Score only jobs posted in the last N days (T02: Manish asked for a window; 7 is Claude's choice until he confirms it). `null` switches the window off; `--posted-within N` / `all` overrides it for one run. Jobs with no posted date are never filtered |
| `relocation_note` | — | Added to cover-letter drafts |
| `countries` | `["India"]` | Where to look (T136–T140): the pre-filter's place rule, the five connectors' searches, rubric rule 1, `discover`'s gate and the Visa column. Built in: India, United Kingdom, Germany, Netherlands, Ireland, United Arab Emirates, Singapore (aliases such as "UK", "UAE", "Holland"); another country by its name. India alone = the original rules. [User guide](00-user-guide.md#looking-for-jobs-outside-india) |
| `home_country` | `"India"` | Where you live: a job in another country needs a visa (rule 1, the Visa column) |
| `titles` | the defaults below | The title part of the pre-filter: `include`, `exclude`, `exceptions` (word lists) and `generic_engineer_titles` (true/false), T103. No block = the defaults; in a block, a list left out is empty. An unknown key, an empty `include` or an entry with other characters than words and `. + # / & -` stops the scan with a message |
| `rubric_file` | — (built-in rubric) | A text file with the scoring rubric, read relative to the working directory, e.g. `"rubric.md"` (T103). `init` writes the built-in one there; `init --resume` rewrites its facts for the person. Without the key the built-in rubric is used |

### `.env` overrides

`GEMINI_API_KEY`, `GEMINI_MODEL`, `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`,
`CLAUDE_CLI_MODEL`, `TELEGRAM_TOKEN` (or
`TELEGRAM_BOT_TOKEN`), `TELEGRAM_CHAT_ID`, and the candidate overrides `CANDIDATE_NAME`,
`RESUME_PATH`, `MIN_SCORE` and `TOP_N`. The `.env` that `autopilot init` writes has these four commented out (T81): an
active line beats `config.json` for every run, and a template that set them live made a new user's edited `config.json` be ignored.

Values from `.env` override both `config.json` and your shell, unless they are
placeholders ([03](03-api-keys.md#precedence)). Every scan logs the values it ended up
using on its first lines (`Min score: … | Top N: …`, `LLM provider: … | Model: …`).

---

## The pre-filter (titles: `config.json` `candidate.titles`; places: `job_hunt/prefilter.py`)

Local, free and deterministic. The **title rules** are word lists in `config.json` (`candidate.titles`, T103); without
them, the **defaults** below apply, written for one profile (Node.js / backend, about 3 YOE, India or remote).
`rolesight init --resume` drafts a person's own lists from their resume, starting from these. An entry matches as
whole words in any case, so `java` doesn't match "JavaScript", `test` doesn't match "Latest", and `intern` doesn't
match "Internal"; spaces and hyphens inside an entry are optional (`back end` also matches "Back-End" and
"backend"). The defaults replaced hand-written regexes and make the same decision on all 34,624 distinct titles of
the 2026-10-13 fetch and the production database (measured 2026-10-14). The **location rules** (India's; other countries' packs in `job_hunt/places.py` when `candidate.countries` names them,
T136) stay in
`job_hunt/prefilter.py`.

They are applied in this order (the default lists):

1. **Title exclude.** If any of these words appears, the job is rejected:
   - Seniority: `lead`, `principal`, `staff` (but not "Member of Technical *Staff*"),
     `manager`, `director`, `architect`.
   - Other stacks: `frontend`, `react`, `angular`, `vue`, `ios`, `android`, `flutter`,
     `java`, `golang`, `.net`, `c#`. (`python` was on this list until T62: Manish allowed it on 2026-10-10,
     so "Python Developer" and "Backend Engineer (Python)" now reach Gemini.)
   - Other roles: `qa`, `quality`, `test`/`tester`/`testing`, `intern`/`internship`, `devops`, `sre`, and (T100) `advocate`, `advocacy`,
     `evangelist`, `devrel`, `developer relations`: developer advocacy is talks, articles and community work, not engineering.

   "Senior" / "Sr." are **not** excluded. At Indian companies they often mean 3–6 years,
   so Gemini judges them (227 India jobs had been blocked by that word alone).
2. **Title include.** At least one of these must appear:
   - `backend`/`back-end`, `node`/`nodejs`/`node.js`.
   - `sde`, `sde2`, …, `software engineer`, `software development engineer`.
   - `member of technical staff`, `mts`.
   - `developer`, `full-stack`, `api`, `distributed systems`.
   - `platform` / `product` / `infrastructure` / `systems engineer`.
   - `AI engineer` (also `Gen AI`, `Generative AI`, `Agentic AI`, `Applied AI`, `LLM engineer`) and `Forward Deployed
     Engineer` (T74, Manish 2026-10-10). These reach Gemini, whose rubric then rejects the ones that need heavy AI (see below).

   - **Generic engineer titles** (T96, Manish 2026-10-14): a title that is only `Engineer` with a seniority or level
     (`Engineer`, `Senior Engineer`, `Sr. Engineer`, `Associate Engineer`, `Engineer II`, `Engineer III, Software`), or has
     `software` and `engineer` in any order (`Sr Software Application Engineer`). Companies name roles differently, so Gemini
     judges the description. `Data Engineer`, `Mechanical Engineer`, `Cloud Engineer` and the like still need an include word.
     Measured on 2026-10-13: 49 more jobs a week reach Gemini, most of them hardware or support roles that score low.

   Not yet included: Adobe's "Computer Scientist" titles (T11). Also, "developer" lets
   CRM roles such as "Salesforce Developer" through (T12).
3. **Location.**
   - **India as a country** (T84, Manish 2026-10-14: he applies to all of India): the word `india` or `IND`, any Indian state or
     union territory, any of the main cities (Bengaluru/Bangalore, Pune, Gurugram/Gurgaon, Hyderabad, Noida, Mumbai, Chennai, Delhi,
     NCR, Kolkata) or some 150 more (Coimbatore, Indore, Nagpur, Bhubaneswar, Lucknow, Kochi, …), or a lowercase trailing
     `, in` country code (SmartRecruiters) → **pass**, even when US cities are listed too. An uppercase `, IN` is Indiana and
     doesn't count. (`LOCATION_INDIA_PATTERN` and `LOCATION_INDIA_MORE_PATTERN` in `prefilter.py`.) Known limit: the lists have no country context, so a foreign place with an Indian name ("Kochi, Japan") also counts as India; such a job still has to pass the title rule, and the fetch of 2026-10-13 had none that did.
   - **Other countries** (`candidate.countries`, T136, T142: any country). India alone takes the rules above unchanged. Every
     country has a pack (`job_hunt/places.py`): hand-made for the UK, Germany, the Netherlands, Ireland, the UAE, Singapore, the
     USA, Canada and Australia; built from [GeoNames](https://www.geonames.org) (CC BY 4.0) for the rest (`job_hunt/data/countries.json`, `scripts/build_countries.py`:
     name, other names, ISO codes, the 8 biggest cities whose name no bigger foreign city shares, regions). A location is read part
     by part (split at `;`, `|`, ` / `, ` or `). A part names a country when it says the country's name, an ISO code where boards
     put one ("Dubai, ARE", "SGP", SmartRecruiters' "Berlin, de", "Munich, DE" at the end), a US state, Canadian province or
     Australian state by name or code ("Austin, TX", "Toronto, ON", "Sydney, NSW"; "Perth, WA" is Australia and "Seattle, WA"
     the USA by their cities), or a code prefix ("US-CA-Dublin", "GB - London"). A city counts unless its own comma segment or
     the next one names another country ("London, Ontario" is Canada, "Aberdeen, MD" the USA); a city-state ("Singapore",
     "Hong Kong") never does. A location then passes when it names one of your countries; when it names a region of one of them
     and no other place ("Remote - EMEA", "Europe" for Germany, "APAC" for Singapore, not "EMEA - UK"); when it says
     worldwide/anywhere/global; or when it is remote and names no place. Rejected otherwise: `Location '…' is not in your places
     (…)`. Measured on the 2026-10-21 and 2026-10-13 fetches (13,015 distinct locations): India's decisions are unchanged on
     111,106 saved jobs; for the six countries of T136, 40 locations changed, all read: US and Australian places that had passed
     as British ("Aberdeen, MD", "Glasgow, Delaware", "Cardiff, NSW") and city lists that now count ("New York, London").
   - **Optional city filter** (`candidate.cities`, e.g. `["Pune", "Hyderabad"]`; empty = all of India or of your countries). A job in an Indian city
     or state that is not one of them is rejected, unless it is remote or names no city (just "India"). Usual alternative names
     match (Bangalore = Bengaluru, Gurgaon = Gurugram), and `"Delhi NCR"` means Delhi, New Delhi, Noida, Greater Noida, Gurugram,
     Ghaziabad and Faridabad. A chosen city the lists do not know still counts as India.
   - Otherwise, a non-India region (`US`, `UK`, `Canada`, `Germany`, `Europe`, `EMEA`,
     `LATAM`, `San Francisco`, `New York`, `Austin`, `Seattle`, `London`, `Berlin`, or
     `, CA|NY|TX|WA|IL|MA`) → **reject**.
   - Otherwise, `worldwide` / `anywhere` / `global` → **pass**.
   - Otherwise, the ATS's remote flag or the word `remote` → **pass only if the location names no place** (T77):
     "Remote", "Hybrid", "Remote Work, More…" and Workday's "3 Locations" / "Location Negotiable" pass; "Paris",
     "Singapore", "Remote - Poland" or "Remote, ie" are rejected (the board flags those offices as remote, but they are not
     workable from India). A place is any word left after removing words like remote, hybrid, APAC and the placeholders; an
     Indian state or city is never a "non-India place".
   - Otherwise → **reject**.
4. **Posted date** (`max_posted_age_days`, default 7, or `--posted-within N`). A job whose
   posted date is known and older than N days is rejected (saved as `skipped`). Jobs
   with **no date always pass**. Dates are parsed from ISO strings, epoch timestamps and
   Workday's "Posted N Days Ago" text, where "30+ Days" counts as 30.

   The window also saves requests (T02): a Workday job outside it gets no per-job detail call, and the
   adapters whose lists are newest first (Oracle HCM, Eightfold, SmartRecruiters) stop paging at the first
   page that holds only older jobs. Amazon is never cut short (its `sort=recent` order is only roughly by
   date, measured 2026-10-10) and neither is any board whose list order is not by date. A board stopped this
   way counts as partly fetched for the closed-job check (T33), with one exception (T78): a stored job whose posted date is
   inside the window (minus a day of margin) and that the board did not return is a real miss, because it would have been on
   the pages read. Older and undated jobs are neither missed nor closed by such a stop. Any other early stop (a failed page, the
   time budget, a job cap) still counts no miss at all.

The rejection reason for each job is logged at DEBUG level in `data/autopilot.log`.

---

## Scoring (`scorer.py` → `llm_utils.score_job_with_gemini`)

One Gemini call per job. The prompt contains:

- an instruction to output only `{"score": <0-100>, "reason": "<one sentence>"}`;
- **the candidate profile**: `name`, `profile`, `seeking`, `not_suitable`;
- **the whole resume** (from `resume_path`);
- **the job**: company, title, location and the full description, cut at 20,000
  characters to guard against runaway pages. Clean descriptions measured at most 10,180
  characters. Before T13, descriptions were cut at 2,000 characters. Re-scoring 16 jobs
  with the full text left every score the same or lower. The average change was 15 points
  on Greenhouse, 26 on SmartRecruiters and 6.7 on Workday, against 3.3 points of
  run-to-run noise (CHANGELOG 2026-10-04).
- **rubric anchors** (`llm_utils.SCORING_RUBRIC`, T48; replaced by `candidate.rubric_file` when set, T103; what follows is
  the built-in rubric): cap 30 for onsite work or work
  authorisation outside India (with `candidate.countries` set to other countries, T138: cap 30 for on-site or hybrid work
  outside them, and for a posting that refuses visa sponsorship or asks for citizenship, permanent residence or an existing
  right to work there; a posting silent on visas is not capped; the same two lines of a `rubric.md` drafted by `init --resume`
  are rewritten too, and a rule 1 you rewrote yourself is used as written, with a warning in the scan log); cap 40 for roles in your `not_suitable` list or platform
  administration of Salesforce, Coupa, SAP or ServiceNow (judged by the work, not the employer's
  name); cap 50 for roles that need 6+ years; cap 50 for roles aimed at freshers or asking 0-1
  years (by what the posting asks, not by its title: T58); cap 50 when the posting's *requirements
  or qualifications* demand a backend language outside your stack and accept none of yours (a posting
  that accepts Python or "another language" is not a mismatch; languages named only in the
  responsibilities, or as examples "such as Java or C#", are a stretch scored 65–84, not a cap;
  TypeScript used only for a frontend part does not count); cap 50 when it *requires*
  an industry, platform or tool you lack (e.g. video-games industry, embedded, SAP), and (T74) when it *requires* hands-on
  AI/ML engineering you have not done: agents built with LangChain/LangGraph-type frameworks, RAG over a vector database,
  fine-tuning or evaluating models, PyTorch/TensorFlow, MLOps, NLP specialisation or years of ML experience. Items under
  "bonus"/"preferred", mere familiarity with LLMs or RAG, and using LLM APIs inside backend work do not trigger it. These two follow
  Manish's rule "skip a posting that requires what I don't have" (T73: false positives 2 → 0 at
  `min_score` 70 on 82 labelled jobs, `apply` 14/14, two runs each); 85+ only when stack, seniority
  and location all fit. The text is tuned to one candidate (about 3.3 years; Node.js, TypeScript,
  Python).
- **Which rubric scored a row** (T97): the rubric has changed several times (T58, T73, T74, T79) and a scored row is final,
  so every new score is stored with `jobs.score_rubric`, 8 hex digits of the SHA-256 of the rubric text
  (`llm_utils.rubric_id()`; the opt-in structured mode has its own id for its own instructions). The scan logs
  `Scoring rubric: <id>` at its start. `python scripts/rubric_ids.py --db data/jobs.db` prints each id with the commit that
  first had that text, and how many scored rows carry each id (`-` = scored before ids were recorded). The id covers the rubric
  text only: a change to the code around the prompt, to your profile or to your resume does not change it. After you edit the
  rubric, the rows with another id are the ones scored under older wording. **Do not reset them all to `discovered`:** a scan
  re-scores only a job it fetches again, that passes today's pre-filter and is inside the posted window. Any other row set back
  to `discovered` is never scored again and drops out of `open_matches.csv` and `export`. In T86, 3 of 145 old rows qualified.
  Pick the rows that qualify (as T86 did, against a fresh fetch), back up `data/jobs.db`, reset only those, then scan: one Gemini
  call each.

Settings: temperature 0.1, JSON output, model fallback and retries as in
[02](02-providers.md). A job with no description is sent as "No full description
provided." Since the enrich step (T19–T22), that should be rare for Workday,
SmartRecruiters and Oracle HCM.

### What a score means

The first real scan (2026-10-04) ran **before** the rubric was added, so these are the model's
own, unanchored scores:

| Score band | Rows in the CSV (226 total) |
|---|---|
| ≥ 80 | 38 |
| 70–79 | 29 |
| 60–69 | 7 |
| < 60 | 152 |

21 jobs tied at exactly 90. Run-to-run noise was 3.3 points on 3 jobs (a small sample).

**How good is the score?** `scripts/score_golden_set.py` scores 75 labelled postings with the
rubric off and on and prints precision, recall, ranking quality (AUC) and ties. Measured
2026-10-04: at `min_score` 70 the rubric cut false positives from 7 to 4 (precision 77% →
85%) while every "apply" job still passed; ranking quality did not change (AUC 0.955 vs
0.956) and the biggest tie among scores ≥ 85 stayed at 10–11 jobs. The labels are Claude's,
not yours, so treat this as a rough estimate until you confirm them (T59). Use the score to
order your reading and the **Reason** to decide.

### `min_score`

This decides what counts as a match: "Worth Applying = Yes" in the CSV, the Telegram
alerts and the digest. It doesn't change what gets scored or stored. On the first scan,
60 → 74 matches and 70 → 67 matches.

The default is 70 (Manish, 2026-10-10). On the 82 labelled jobs rubric v7 (T73, before T74's AI clause) passes no `no` job at
60 or at 70 and finds all 14 `apply` jobs at both (2 runs); 70 drops at most one `maybe`. The pre-T73 rubric's
precision was 92% at 70 against 83% at 60. Set it in `config.json` (`candidate.min_score`) and nowhere else: a `MIN_SCORE` line
in `.env` still overrides it for every run, and `run_daily.sh` sets none (T05). The scan's first log lines show the
value in force (`Min score: 70`).

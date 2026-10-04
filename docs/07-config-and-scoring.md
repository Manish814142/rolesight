# 07 — Config & scoring

## `config.json` reference

The file is gitignored; start from `config.example.json`. Any key can be left out, and
the default shown applies.

### Top level

| Key | Default | Used for |
|---|---|---|
| `llm_provider` | `gemini` | Drafting, and scoring when no Gemini key is set ([02](02-providers.md)) |
| `gemini_api_key` | — | Scoring. Usually set as `GEMINI_API_KEY` in `.env` instead |
| `gemini_model` | `gemini-3.5-flash-lite` | Primary scoring model; the fallback is `gemini-3.1-flash-lite` |
| `gemini_scoring_mode` | `single` | `batch` scores several jobs per call. Faster, but measured to inflate scores ([02](02-providers.md#batch-mode-opt-in-not-recommended)) |
| `gemini_batch_size` | `10` | Jobs per call in batch mode |
| `fetch_workers` | `8` | Companies fetched in parallel; also used for description fetching |
| `telegram.token`, `telegram.chat_id` | — | Optional alerts ([05](05-outputs-and-notifications.md#telegram-optional)) |
| `anthropic_api_key`, `anthropic_model` | — | `llm_provider: anthropic` |
| `claude_cli_model` | Claude's default | `llm_provider: claude_cli` |
| `tinyfish_api_key` | — | Legacy careers-page path and `draft` only. Not used in this fork (T40, T50) |
| `openrouter_api_key`, `openrouter_model`, `openrouter_fallback_models` | — | Deprecated provider |

### `candidate`

| Key | Default | Used for |
|---|---|---|
| `name` | "the candidate" | Prompt context |
| `resume_path` | `resume/YOUR_RESUME.md` | Resume file sent **in full** with every scoring call |
| `profile` | — | One-line summary in every scoring prompt ("3 YOE backend, Node.js…") |
| `seeking` | — | What the candidate wants (roles, cities, remote), in every prompt |
| `not_suitable` | — | What to score low, in every prompt |
| `min_score` | `55` (the code default; the example config uses 60) | Score that counts as a match: "Worth Applying", Telegram alerts, the digest |
| `top_n` | `5` | How many matches the digest and the log summary show |
| `max_posted_age_days` | off | Score only jobs posted in the last N days; same as `--posted-within N` (T02 decides the default) |
| `relocation_note` | — | Added to cover-letter drafts |
| `search_seniority`, `search_keywords` | — | Legacy TinyFish search only. Ignored by the ATS pipeline |

### `.env` overrides

`GEMINI_API_KEY`, `GEMINI_MODEL`, `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`,
`CLAUDE_CLI_MODEL`, `TINYFISH_API_KEY`, `OPENROUTER_*`, `TELEGRAM_TOKEN` (or
`TELEGRAM_BOT_TOKEN`), `TELEGRAM_CHAT_ID`, and the candidate overrides `CANDIDATE_NAME`,
`RESUME_PATH`, `MIN_SCORE` and `TOP_N`.

Values from `.env` override both `config.json` and your shell, unless they are
placeholders ([03](03-api-keys.md#precedence)). Every scan logs the values it ended up
using on its first lines (`Min score: … | Top N: …`, `LLM provider: … | Model: …`).

---

## The pre-filter (`job_hunt/prefilter.py`)

Local, free and deterministic. The rules are **hardcoded for one profile** (Node.js /
backend, about 3 YOE, India or remote). That's deliberate: this is a personal fork. The
patterns are case-insensitive and word-bounded, so `java` doesn't match "JavaScript",
`test` doesn't match "Latest", and `intern` doesn't match "Internal".

They are applied in this order:

1. **Title exclude.** If any of these words appears, the job is rejected:
   - Seniority: `lead`, `principal`, `staff` (but not "Member of Technical *Staff*"),
     `manager`, `director`, `architect`.
   - Other stacks: `frontend`, `react`, `angular`, `vue`, `ios`, `android`, `flutter`,
     `java`, `golang`, `python`, `.net`, `c#`.
   - Other roles: `qa`, `test`/`tester`/`testing`, `intern`/`internship`, `devops`, `sre`.

   "Senior" / "Sr." are **not** excluded. At Indian companies they often mean 3–6 years,
   so Gemini judges them (227 India jobs had been blocked by that word alone).
2. **Title include.** At least one of these must appear:
   - `backend`/`back-end`, `node`/`nodejs`/`node.js`.
   - `sde`, `sde2`, …, `software engineer`, `software development engineer`.
   - `member of technical staff`, `mts`.
   - `developer`, `full-stack`, `api`, `distributed systems`.
   - `platform` / `product` / `infrastructure` / `systems engineer`.

   Not yet included: Adobe's "Computer Scientist" titles (T11). Also, "developer" lets
   CRM roles such as "Salesforce Developer" through (T12).
3. **Location.**
   - An Indian city (Bengaluru/Bangalore, Pune, Gurugram/Gurgaon, Hyderabad, Noida,
     Mumbai, Chennai, Delhi, NCR, Kolkata), the word `india`, or a lowercase trailing
     `, in` country code (SmartRecruiters) → **pass**, even when US cities are listed too.
     An uppercase `, IN` is Indiana and doesn't count.
   - Otherwise, a non-India region (`US`, `UK`, `Canada`, `Germany`, `Europe`, `EMEA`,
     `LATAM`, `San Francisco`, `New York`, `Austin`, `Seattle`, `London`, `Berlin`, or
     `, CA|NY|TX|WA|IL|MA`) → **reject**.
   - Otherwise, `worldwide` / `anywhere` / `global` → **pass**.
   - Otherwise, the ATS's remote flag or the word `remote` → **pass** (remote with no
     geography).
   - Otherwise → **reject**.
4. **Posted date** (only with `--posted-within N` / `max_posted_age_days`). A job whose
   posted date is known and older than N days is rejected (saved as `skipped`). Jobs
   with **no date always pass**. Dates are parsed from ISO strings, epoch timestamps and
   Workday's "Posted N Days Ago" text, where "30+ Days" counts as 30.

The rejection reason for each job is logged at DEBUG level in `scan.log`.

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
- **rubric anchors** (`llm_utils.SCORING_RUBRIC`, T48): cap 30 for onsite work or work
  authorisation outside India; cap 40 for roles in your `not_suitable` list or platform
  administration (Salesforce, Coupa, ServiceNow); cap 50 for roles that need 6+ years; cap 60
  when every language the posting accepts is outside your stack (a posting that accepts
  Python, or "another language", is not a mismatch); 85+ only when stack, seniority and
  location all fit. The text is tuned to one candidate (about 3.3 years; Node.js, TypeScript,
  Python).

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

Which value applies today depends on where it's set: `.env`'s `MIN_SCORE` currently beats
`run_daily.sh`'s 70 (T05). Check the `Min score:` log line.

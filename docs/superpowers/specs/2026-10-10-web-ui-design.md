# T45 — A web page to set up and use RoleSight (design proposal)

**Status: proposal for Manish's review. Nothing in this document is built.** The brainstorming process for a new
subsystem requires an approved written spec, then an approved plan, before any code. Section 7 lists what I need from you.

## 1. What you asked for (your words, 2026-10-10)

> "everything will be web page instead of terminal. it will become easy for a person to configure A-Z things like
> setting resume, title include, exclude, location set key, etc … we can also do the genai call to make the
> configuration better and suggest to user if a person not clear about the things because suppose a person set wrong
> profile then he will get wrong job notification."

My reading, in order of how sure I am:

1. **(sure)** A local web page replaces the terminal for day-to-day use: set up, look at matches, mark applications.
2. **(sure)** Everything that shapes what you are shown is editable there: resume, profile text, title include / exclude
   words, locations, score threshold, posted-date window.
3. **(sure)** Gemini helps while configuring: it suggests values from the resume and warns when a setting contradicts
   the profile ("a wrong profile gives wrong notifications").
4. **(assumed)** It runs on your own machine, for you, and others could later use the same tool on theirs. It is *not*
   a hosted service with accounts. **Question 1 depends on this.**
5. **(assumed)** The invariants stay: drafts only, never auto-apply; secrets never shown or committed.

## 2. What exists today, and what it means for this feature (measured by reading the code, 2026-10-10)

| Today | Consequence |
|---|---|
| Title include/exclude and location rules are **hardcoded regexes** in `job_hunt/prefilter.py`; the board rejected a config-driven filter earlier ("a hardcoded personal filter is fine") | Your request reopens that. The UI needs the rules in `config.json` as plain phrase lists, **with today's rules as the defaults so behaviour does not change**. |
| The **scoring rubric** (`llm_utils.SCORING_RUBRIC`) names *your* facts: "~3.3 years", "Node.js, TypeScript, Python…", "has used GenAI/LLM APIs inside backend services" | For another person the rubric would score against the wrong person. For you alone it is fine. **Question 1.** |
| Profile text (`profile`, `seeking`, `not_suitable`) is already in `config.json` and goes into every scoring prompt | The settings page edits exactly these; no new concept. |
| `data/jobs.db` already holds every job ever fetched, **including the rejected ones** (30,367 rows on 2026-10-07) with title and location | A "preview" is possible without any network: replay your edited rules over stored jobs and show what changes. This is the best protection against a wrong filter. |
| Reading/marking jobs: `autopilot export`, `mark`, `draft`, `open_matches.csv` | The dashboard calls the same functions; it adds no new data. |
| Dependencies: `requests`, `google-genai`, `python-dotenv`, `pyyaml` only | A web framework would be a new dependency. |

## 3. Decomposition (five independent pieces; each gets its own plan, built in this order)

| # | Piece | Why this order | Size |
|---|---|---|---|
| S1 | **Config-driven pre-filter** (`filters` section in `config.json`, defaults = today's rules). No UI. | Everything else edits it. Provable on its own: the survivors of the 39,873 jobs saved on 2026-10-08 must be *identical* (1,900) with the defaults. | M |
| S2 | **`autopilot ui`**: local server + one **Settings** page (resume, profile, filters, thresholds, window) with the **filter preview** over stored jobs. | The piece that answers your request. | L |
| S3 | **Matches** page: the scored jobs (filter, sort, reason, open posting, keyword gaps from T44, mark applied / interview / rejected / offer from T38). Reads `data/jobs.db`. | Needs only existing functions. | M |
| S4 | **Setup assistant** (Gemini): from the resume, suggest profile text, include/exclude words, locations; flag contradictions; every suggestion is shown as a diff you accept or reject, never applied silently. | Needs S1 + S2; costs Gemini calls (a handful per use). | M |
| S5 | **Companies** page: paste names → the existing `discover --add-file` flow, show the report, accept. | Reuses `discovery.py`; optional. | S |

## 4. Approaches for the server (S2), with my recommendation

| | A. stdlib `http.server` + plain HTML/JS (**recommended**) | B. FastAPI/Flask + templates | C. static page + CLI writes JSON |
|---|---|---|---|
| New dependency | none | yes (a web framework, an ASGI server) | none |
| Fits a single local user | yes | yes | clumsy (the page cannot save) |
| Multi-user / hosting later | would need a rewrite | natural | no |
| Test without network | yes (call the handler directly) | yes | yes |
| Cost to build | M | M | S but cannot meet "configure in the page" |

I recommend A **if Question 1 is "local, mostly for me"**. If you want others to use it (or host it), B is the better base and
this section changes; say so before I plan.

## 5. Design (S1–S4)

**Config (S1).** New optional section; absent = today's behaviour:

```json
"filters": {
  "title_include":    ["backend", "node.js", "software engineer", "sde", "full stack", "ai engineer", "…"],
  "title_exclude":    ["lead", "principal", "staff", "manager", "frontend", "java", "golang", "…"],
  "title_exceptions": ["member of technical staff"],
  "location_include": ["bengaluru", "pune", "hyderabad", "india", "…"],
  "location_exclude": ["united states", "london", "…"],
  "remote": "when-no-region"
}
```

A phrase matches whole words, any case; space, hyphen and nothing are interchangeable ("back end" = "back-end" = "backend");
symbols are literal (".net", "c#", "c++"). The two special cases in today's regexes ("technical staff" is allowed;
"Embedded Finance" is an accepted loss) become `title_exceptions` and a documented note. `prefilter.py` builds its
patterns from this at start-up; the old constants become the defaults. **Acceptance test (S1):** the defaults reproduce
today's decisions on all 39,873 saved jobs (survivor sets equal), plus unit tests per phrase form.

**Server (S2).** `autopilot ui [--port 8765]` binds **127.0.0.1 only**, serves one HTML page and a small JSON API:
`GET/PUT /api/settings`, `POST /api/resume`, `POST /api/preview` (rules in the body → counts and 20 sample titles that
would newly pass / newly fail over stored jobs), `GET /api/jobs`, `POST /api/mark`. Writes go to `config.json` atomically
(temp file + rename) after validation (score 0–100, window ≥ 0 or null, phrases non-empty, at least one include phrase).
API keys and Telegram secrets are **not** editable or displayed in the page (they stay in `.env`; the page shows only
"Gemini key: set / not set"). Every state-changing request carries a random token printed at start-up, so another web page
open in your browser cannot drive it.

**Assistant (S4).** One endpoint sends the resume and current settings to Gemini with a fixed instruction and returns
structured suggestions plus warnings; the page shows each as a before/after you accept one by one. **Privacy:** this sends
your resume to Google, as scoring already does; the page says so next to the button. Suggestions are not scored against a
labelled set, so they are advice, not truth; the preview is the check.

**Errors.** Invalid settings are rejected with the field and reason, `config.json` is untouched; a Gemini failure shows a
message and changes nothing; an unreadable `jobs.db` shows an empty Matches page with the reason.

**Testing.** No network: handlers are called directly, Gemini is stubbed, `jobs.db` is a temp file. The server is also started
once in a test on a random port and fetched with `requests` (localhost only). Gates as always (pytest, ruff, mypy, 85%).

## 6. Risks I already see

- **Wrong filter = silent loss of jobs.** Mitigations: defaults identical to today, the preview, a "reset to defaults" button,
  and the funnel line on the Matches page ("rejected by title: N").
- **The rubric is personal** (Section 2). Without a change, another user's scores would be wrong; with a change (rubric built from
  the profile) every rubric edit needs the golden-set measurements again (164 Gemini calls each, as T48/T73/T74 did).
- **Scope.** S1–S5 together are several days. I will only start S1 after you approve this document.

## 7. What I need from you

1. **Who is this for?** (a) only you, (b) you now and friends later, each on their own machine, (c) a hosted service.
   My recommendation and the default of this document: (a)/(b). It decides Section 4 and whether the rubric must be rebuilt per person.
2. **Is S1–S5 the right set and order?** Anything missing (for example editing `companies.json` by hand, or changing the
   Gemini model from the page)?
3. **Which page do you want first after S1?** Settings (S2) or Matches (S3)? I recommend Settings, since that is where wrong
   configuration costs you.
4. **Gemini help (S4):** suggestions only on request (button), or also an automatic warning each time you save? I recommend the button.
5. **May the page edit `config.json` directly?** (It rewrites the file; I keep a `config.json.bak` of the previous version.)

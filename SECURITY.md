# Security

RoleSight fetches public job listings, sends a resume to an LLM for scoring, and can
post alerts to Telegram. This page states what it guarantees and where the trust
boundaries are. For exactly which data goes where, see [PRIVACY.md](PRIVACY.md).

## The never-apply invariant

**RoleSight never applies to a job or submits anything on anyone's behalf.** It only:

- fetches public job listings and scores them,
- writes CSVs, and (with `autopilot draft`) a tailored resume and cover letter, to
  `output/` for a human to review,
- optionally sends alerts to your own Telegram chat.

There is no apply, submit or form-filling capability anywhere in the code. Every change
is reviewed against this invariant ([docs/tasks.md](docs/tasks.md) → *Verifying*). Don't
extend the tool to auto-apply.

## Trust boundaries

- **Secrets.** `GEMINI_API_KEY`, the optional `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` and
  any other keys live in `.env` / `config.json`, which are both gitignored. Rotate any key
  that may have leaked. CI scans every push and the whole history with gitleaks
  (`.github/workflows/ci.yml`; `.gitleaks.toml` allowlists only the golden-set CSVs), but check staged diffs yourself too.
- **The resume is personal data.** The real resume (`resume/<name>.md`) is gitignored; only
  the template is committed. Its full text is sent to Gemini with every scoring call.
- **ATS endpoints are untrusted input.** Job titles, locations and descriptions come from
  third-party servers. They are parsed as data (JSON/XML) and stripped of HTML, never
  executed. Every HTTP response has a hard total deadline (900 s), so a hostile or broken
  server can't hang a scan.
- **Telegram (opt-in).** Alerts contain the company, title, location, score, reason and
  URL. They go to Telegram's servers and into your own chat.

## Prompt injection

Job descriptions are pasted into the scoring prompt in full (up to 20,000 characters), and
into the drafting prompts. A posting could contain text meant to steer its own score or a
drafted cover letter. Mitigations:

- The output is only a number and one sentence, and the model is asked for JSON only.
  Nothing the model returns is executed.
- A score only orders what a human reads; a human always decides and applies.
- Drafts are local files for review, never sent anywhere.

Don't extend the tool to act on instructions found in job content, and treat an
implausibly high score with a generic reason as a sign of injection.

## Fetching etiquette

The ATS endpoints are the public job-board APIs that the vendors provide for listing
jobs. RoleSight fetches 8 companies at a time, once per scan, with a browser-like
User-Agent. Whoever runs it is responsible for keeping within each site's terms and rate
limits. Don't raise `fetch_workers` aggressively or run scans in a tight loop.

## Reporting a problem

Open an issue on the project's GitHub page for anything that isn't sensitive. For a security
problem, use GitHub's private vulnerability reporting (the repository's Security tab) instead of a public issue.

## Supported versions

Only the current `main`.

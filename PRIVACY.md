# Privacy: what leaves the machine

JobNotify runs locally. This page lists every outbound destination in the code and what
each one receives. It was checked against the source on 2026-10-04.

## The short version

- **Your resume goes to Google.** The full resume text, plus the candidate profile from
  `config.json`, is sent to the Gemini API with **every** scoring call. The first full
  scan made 226 such calls.
- **Job boards see only requests for public listings.** No personal data is sent to them.
- **Everything else is opt-in:** Telegram alerts, and drafting (which uses your chosen
  LLM provider and, for now, TinyFish).
- **It never applies to a job** ([SECURITY.md](SECURITY.md)).

## Outbound destinations

| Destination | When | What it receives |
|---|---|---|
| ATS job boards: Greenhouse, Lever, Ashby, SmartRecruiters, Workday tenants, Oracle HCM tenants, Amazon Jobs, Workable, Recruitee, Personio | Every scan, and `discover` / `doctor` | Requests for public job listings and job details. Your IP address and a browser-like User-Agent. **No resume or profile data.** |
| **Google Gemini API** (`generativelanguage.googleapis.com`) | Every scoring call; one tiny call per `doctor` run | **The full resume, the candidate profile** (name, profile, seeking, not-suitable) and the job's title, company, location and description |
| Telegram (`api.telegram.org`) | Only if `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` are set | Per-job alerts and the digest: company, title, location, score, reason, URL |
| Your `llm_provider` (Gemini, Anthropic, local `claude` CLI, or OpenRouter, deprecated) | `autopilot draft` only | The resume, the profile and the job description, to write the drafts |
| TinyFish (`agent.tinyfish.ai`) | `autopilot draft` only, and only with a TinyFish key; also the unused legacy careers-page path | The job URL to fetch. This fork doesn't use TinyFish (T40 removes the dependency) |

**About Gemini's free tier.** Google's terms for unpaid Gemini API use have allowed it to
use submitted content to improve its products, which can include human review. That is
*assumed* from Google's published terms at the time of writing; read the current terms
before relying on it. If that matters for your resume, use a paid Gemini key, or remove
personal details (phone, email, address) from the resume file. Scoring doesn't need them.

Not active: `notifier.send_whatsapp` (TextMeBot) exists in the code, but nothing calls it.

## What is stored locally (all gitignored)

| Path | Contains |
|---|---|
| `resume/<name>.md` | Your resume (personal data) |
| `config.json`, `.env` | Candidate profile and API keys |
| `data/jobs.db` | Jobs seen, statuses, scores and reasons. Job data only, no resume |
| `state/*.json` | Scored jobs (last scan, history), seen URLs |
| `output/` | CSVs. Drafts (`output/<company>-<date>/`) contain your personal content |
| `scan.log`, `data/scan.log` | Run logs: job titles, scores and reasons. No keys |

## Telemetry

None. JobNotify sends no analytics, usage pings or crash reports.

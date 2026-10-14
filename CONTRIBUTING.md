# Contributing

RoleSight is Manish's project. The work is done by him and the AI agents working for
him (Claude Code, Antigravity); issues and pull requests from others are welcome and go through the same gates.
This page is the short version of how work gets done; the details live in the task board.

## Where work comes from

**[docs/tasks.md](docs/tasks.md)** is the single board. For a first look at what could be extended (other countries than
India, more job boards, the ideas not started yet), read [docs/10 — Limitations and future work](docs/10-limitations-and-future-work.md).

- **Implementing:** follow its *Working loop*. Pick the next task in priority order, claim
  it, implement it with tests, run its *Done when* check plus the gates, commit, and add
  it to the *Review queue* with the exact commands and output.
- **Verifying:** follow its *Verifying* section. Re-run the checks yourself, then pass
  the task to the *Done log* or send it back with review notes.
- **New findings:** add them to the board's *Inbox*. Don't fix them inside another task's
  commit.
- **Order:** accuracy tasks come first (anything that changes what Gemini sees, how it
  scores, or which jobs reach it). See the board's *Accuracy-first order*.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[gemini,dev,mcp]'
```

## Gates (all must pass before a commit)

```bash
pytest               # coverage gate 85%
ruff check job_hunt/ tests/ conftest.py
mypy
```

More on testing: [docs/09-testing-checklist.md](docs/09-testing-checklist.md).

## Rules

- **Drafts only.** Never add anything that applies, submits or fills in a form.
- **No network in tests.** Stub the adapters, Gemini and Telegram.
- **`companies.json` is curated.** Change it only through `autopilot discover`, and review
  `git diff companies.json` before committing. Never regenerate it with `harvest` or
  `validate`.
- **No secrets or PII in git.** `.env`, `config.json`, `resume/*.md` (except the
  template), `data/`, `state/` and `output/` are gitignored. Keep it that way.
- **Measure, then claim.** CHANGELOG entries and review evidence say what was
  *measured* (with the number and the command), what is *inferred* and what is
  *assumed*. Don't write "verified" for a check that wasn't run.

## Commits

- **One task per commit.** The message starts with the task ID:
  `T03: stop scoring when the Gemini quota is exhausted`. Board-only updates use
  `tasks: …`.
- **Stage only your own files** (`git add <paths>`, never `git add -A`). Another agent may
  be working in the same tree.
- **Commit on `main`.** The remote `upstream` is the original project (autopilot-jobhunt), kept read-only
  to compare against; this project's own repository is `origin`.
- **Record the change** in [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`.

## Code of conduct

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

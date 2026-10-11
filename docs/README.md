# JobNotify documentation

JobNotify fetches open jobs from the public ATS APIs of about 215 India-hiring companies,
filters them locally, scores the survivors against a resume with Gemini, and writes a
best-first CSV. It **never applies** to anything. The project overview is in the
[top-level README](../README.md).

## Guides

| # | Guide | Covers |
|---|---|---|
| 00 | [User guide](00-user-guide.md) | Which file and which setting to change, step by step: install, resume, profile, word lists, companies, reading the CSV |
| 01 | [Install & first run](01-install.md) | venv, extras, `.env` / `config.json`, resume, `doctor`, the first scan |
| 02 | [LLM providers](02-providers.md) | Gemini (default) models, retries, quotas, batch mode; Anthropic; Claude CLI |
| 03 | [API keys](03-api-keys.md) | Which keys exist, which are required, precedence |
| 04 | [Companies & scanning](04-companies-and-scanning.md) | `companies.json`, `discover` (add / recheck / census), what a scan does, per-ATS details, timings |
| 05 | [Outputs & notifications](05-outputs-and-notifications.md) | CSV columns, DB statuses, state files, logs, `export`, drafts, Telegram |
| 06 | [MCP server & skill](06-mcp-and-skill.md) | Using JobNotify from Claude Code |
| 07 | [Config & scoring](07-config-and-scoring.md) | Every config key; the pre-filter rules; the scoring prompt and what scores mean |
| 08 | [Troubleshooting](08-troubleshooting.md) | Known symptoms, causes and fixes |
| 09 | [Testing checklist](09-testing-checklist.md) | Gates, smoke tests, a real small scan, MCP check |
| — | [Task board](tasks.md) | Pending work by priority; how agents claim, finish and verify tasks |

## Also see

- [ARCHITECTURE.md](../ARCHITECTURE.md): components, data flow, rules, known limitations.
- [CHANGELOG.md](../CHANGELOG.md): what changed and the measurements behind it.
- [SECURITY.md](../SECURITY.md) and [PRIVACY.md](../PRIVACY.md): guarantees, and what
  leaves the machine.
- [CONTRIBUTING.md](../CONTRIBUTING.md): how work is picked up.

## Reading order

- **Using it, or changing how it behaves:** [00 — User guide](00-user-guide.md).
- **New to the project:** [README](../README.md) → [01](01-install.md) →
  [04](04-companies-and-scanning.md) → [05](05-outputs-and-notifications.md).
- **Changing code:** [ARCHITECTURE.md](../ARCHITECTURE.md) → [07](07-config-and-scoring.md)
  → [09](09-testing-checklist.md) → [tasks.md](tasks.md).

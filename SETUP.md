# Setup

The setup guide now lives in **[docs/01-install.md](docs/01-install.md)**. It covers
install, keys, config, resume, `autopilot doctor`, the first scan and running it daily.

In short:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[gemini,dev]'
cp config.example.json config.json         # candidate profile
cp job_hunt/data/env_example .env          # GEMINI_API_KEY
autopilot doctor
autopilot scan --posted-within 7
```

Only a Gemini API key is required. TinyFish and OpenRouter, which the upstream
project's setup needed, are not used by this fork. Use the repo's `companies.json`
(215 India-hiring boards); `autopilot init` copies an outdated upstream list (T50).

More: [README](README.md) · [all docs](docs/README.md) ·
[MCP / Claude Code](docs/06-mcp-and-skill.md) · [troubleshooting](docs/08-troubleshooting.md)

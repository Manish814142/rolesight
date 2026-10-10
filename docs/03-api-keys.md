# 03 — API keys

| Key | Needed for | Required? | Get it |
|---|---|---|---|
| `GEMINI_API_KEY` | Scoring (and `doctor`'s Gemini check) | **Yes** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey), free |
| `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` | Alerts | No | [@BotFather](https://t.me/BotFather); see [05](05-outputs-and-notifications.md#telegram-optional) |
| `ANTHROPIC_API_KEY` | Drafting with `llm_provider: anthropic` | No | [console.anthropic.com](https://console.anthropic.com) |

The ATS APIs themselves need **no keys**. They are public job-board endpoints.

## Where keys go

Put them in **`.env`** in the repo root (gitignored):

```bash
GEMINI_API_KEY=your-key
# TELEGRAM_TOKEN=123456:ABC...      # TELEGRAM_BOT_TOKEN also works
# TELEGRAM_CHAT_ID=123456789
```

You can also put them in `config.json` (`gemini_api_key`, `telegram.token`,
`telegram.chat_id`, …), which is also gitignored.

## Precedence

1. `config.json` is read first.
2. Values from `.env` then override it, and also override variables already exported in
   your shell (`load_dotenv(override=True)`).
3. A value that is still a template placeholder (`YOUR_…`, `…_here`, `…_HERE`) is
   ignored. A placeholder Telegram value counts as "not configured".

Rule 2 means a `MIN_SCORE=` line in `.env` beats `candidate.min_score` in `config.json`. Since T05 the
`.env` template has no such line and `run_daily.sh` exports none, so `config.json` is the one place (default 70).
Check the `Min score:` line at the top of a scan's log to see the value in force.

## Verify

```bash
autopilot doctor
```

`[PASS] Gemini Quota` means the key works. Telegram shows `WARN` when it isn't
configured, which is fine, and `FAIL` when it is configured but rejected.

## Next

- [04 — Companies & scanning](04-companies-and-scanning.md)

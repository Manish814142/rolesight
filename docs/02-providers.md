# 02 — LLM providers

JobNotify uses an LLM for two things: **scoring** jobs (every scan) and **drafting**
applications (`autopilot draft`, on demand). The two choose their provider differently.

## Who does the scoring

| Situation | Scoring path |
|---|---|
| A Gemini key is set (`GEMINI_API_KEY` in `.env`, or `gemini_api_key` in `config.json`) | **Gemini, always**, whatever `llm_provider` says. One job per call, results stored in `data/jobs.db`. This is the supported path. |
| No Gemini key | Legacy path: `llm_provider` scores 10 jobs per prompt, with a shorter resume and description cut. Its scores are **not written to the DB**, so the same jobs are re-scored on every scan (read in `scanner.py`, not run). Don't rely on it. |

`llm_provider` also picks the model for `autopilot draft`.

## Gemini (default)

- **Models:** `gemini_model` (default `gemini-3.5-flash-lite`). If it fails, the
  fallback is `gemini-3.1-flash-lite`. Set the model in `config.json`, or with
  `GEMINI_MODEL` in `.env`.
- **Call:** temperature 0.1, JSON output `{"score": 0-100, "reason": "<one sentence>"}`.
- **Retries:** on a 429 / 503 / quota error, each model gets one retry after 5–15 s
  (using the server's "retry in N s" hint when there is one), then the next model is
  tried. If every model fails, the job stays `discovered` and is retried next scan. A
  failure is never stored as a score of 0. A 429 whose quota is **per day** is not
  retried: that model is skipped until the reset time Google gives, so a dead primary
  costs one request per run instead of two requests and a 5 s wait per job (T64).
- **Pacing:** a 4.2 s sleep after every scoring call, to stay under 15 requests per
  minute. Measured: about 6.3 s per job including the call (226 jobs in about 24 min,
  2026-10-04).
- **Free-tier limits** (Google's published figures, as recorded in CLAUDE.md, not
  verified live): 15 requests per minute, 250k tokens per minute and **500 requests per
  day per model**. With 2 models that is roughly 1,000 scoring calls a day.
  Use `--posted-within N` to keep a scan inside that budget. A scan stops scoring
  once 3 jobs in a row fail with a quota error on every model (T03), and scores at most
  `max_jobs_to_score_per_run` jobs (default 400), newest first (T04); the rest wait for the next scan.
- **Model choice:** `gemini-3.8-flash` (20 requests a day) and `gemini-flash-latest` are
  deliberately not used as fallbacks, so a fallback never burns a tiny quota.

### Batch mode (opt-in, not recommended)

`"gemini_scoring_mode": "batch"` in `config.json` scores `gemini_batch_size` jobs (default
10) per call, with a JSON schema. It's about 17× faster. On 10 live jobs, batch scores
differed from single-job scores by 15.5 points on average, against 1.0 point of
run-to-run noise, and weak fits were inflated (measured 2026-10-04, CHANGELOG). Accuracy
matters more than speed here, so single-job scoring is the default.

## Anthropic API (drafting, or scoring without a Gemini key)

```bash
pip install -e '.[claude]'
```

```json
"llm_provider": "anthropic",
"anthropic_api_key": "sk-ant-...",
"anthropic_model": "claude-haiku-4-5-20251001"
```

Or set `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` in `.env`.

## Claude Code CLI (keyless)

```json
"llm_provider": "claude_cli",
"claude_cli_model": ""
```

This uses the local `claude` binary and its login, so no API key is needed. Check it first
with `claude --print "hi"`. Each call loads your Claude Code context, which costs a lot of
subscription usage, so use it for an occasional draft, not for daily scoring.

## OpenRouter (removed)

`llm_provider: "openrouter"` was removed (T42); a config that still names it fails with a
message telling you to use `gemini`, `anthropic` or `claude_cli`.

## Next

- [03 — API keys](03-api-keys.md)
- [07 — Config & scoring](07-config-and-scoring.md): the scoring prompt and threshold.

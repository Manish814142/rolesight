import json
import os
import re
import subprocess
import time
import warnings
from typing import Any, cast

from openai import OpenAI, RateLimitError

from job_hunt.log import get_logger

warnings.filterwarnings("ignore", message=".*automatic function calling.*")

logger = get_logger()

# Per-request timeout (seconds) for HTTP-based LLM providers. Without this the
# openai/anthropic SDKs default to 600s, so a single stalled free-tier model can
# freeze a scan for 10 minutes. claude_cli has its own subprocess timeout (300s).
_LLM_REQUEST_TIMEOUT = 120.0

_openrouter_deprecation_warned = False


def _make_openrouter_client(config: dict) -> OpenAI:
    return OpenAI(
        api_key=config.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        timeout=_LLM_REQUEST_TIMEOUT,
    )


def _chat_with_anthropic(config: dict, messages: list[dict], temperature: float, max_tokens: int) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError("Run: pip install 'autopilot-jobs[claude]'")
    api_key = config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    model = config.get("anthropic_model", "claude-haiku-4-5-20251001")
    logger.debug(f"LLM call → Anthropic / {model}")
    t0 = time.time()
    client = anthropic.Anthropic(api_key=api_key, timeout=_LLM_REQUEST_TIMEOUT)
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_msgs = [m for m in messages if m["role"] != "system"]
    kwargs: dict = {
        "model": model,
        "messages": user_msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system:
        kwargs["system"] = system
    r = client.messages.create(**kwargs)
    elapsed = time.time() - t0
    text = r.content[0].text
    logger.debug(f"LLM response: {len(text)} chars in {elapsed:.1f}s (input={r.usage.input_tokens} out={r.usage.output_tokens} tokens)")
    return text


def _chat_with_claude_cli(config: dict, messages: list[dict], temperature: float, max_tokens: int) -> str:
    model = config.get("claude_cli_model", "")
    logger.debug(f"LLM call → Claude CLI{' / ' + model if model else ''}")
    t0 = time.time()

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_msgs = [m for m in messages if m["role"] != "system"]
    prompt_text = "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in user_msgs)

    # --strict-mcp-config suppresses all MCP servers in the subprocess; reduces ~27k context tokens
    cmd = [
        "claude", "--print", "--output-format", "json", "--tools", "",
        "--mcp-config", '{"mcpServers":{}}', "--strict-mcp-config",
        "--disable-slash-commands",
    ]
    if system:
        cmd += ["--system-prompt", system]
    if model:
        cmd += ["--model", model]

    try:
        result = subprocess.run(
            cmd,
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "claude binary not found in PATH.\n"
            "Install Claude Code from https://claude.ai/code and run 'claude auth login'."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after 300s.")

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exited {result.returncode}: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            text = data.get("result")
            if text is None:
                raise KeyError("no 'result' field in output")
        elif isinstance(data, list):
            result_event = next((e for e in data if isinstance(e, dict) and e.get("type") == "result"), None)
            if result_event is None:
                raise KeyError("no 'result' event found in output")
            text = result_event["result"]
        else:
            raise TypeError(f"unexpected output type: {type(data)}")
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        raise RuntimeError(f"claude CLI unexpected output ({e}): {result.stdout[:200]}")

    elapsed = time.time() - t0
    logger.debug(f"LLM response: {len(text)} chars in {elapsed:.1f}s via claude CLI")
    return text


def _get_genai_client_and_types(api_key: str | None = None):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("google-genai is not installed. Run: pip install google-genai")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    return client, types


GEMINI_DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Only high-quota free-tier models (500 RPD each). gemini-3.8-flash (20 RPD) and the
# "latest" alias are deliberately excluded so a fallback never burns a tiny quota.
GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]


def _gemini_models(config: dict) -> list[str]:
    primary = config.get("gemini_model") or os.getenv("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL
    return [primary] + [m for m in GEMINI_FALLBACK_MODELS if m != primary]


class GeminiQuotaExhausted(RuntimeError):
    """Every model in the fallback chain answered with a rate-limit / quota error (T03).

    Scoring more jobs cannot succeed until the quota resets, so callers may stop early.
    """


def _is_quota_error(message: str) -> bool:
    return any(t in message for t in ("429", "RESOURCE_EXHAUSTED", "ResourceExhausted", "quota"))


def _generate_with_fallback(client: Any, contents: str, cfg: Any, models: list[str]) -> str:
    """Call generate_content across `models`, retrying once on rate-limit/transient errors.

    Raises GeminiQuotaExhausted when every model failed with a quota error.
    """
    last_err: Exception | None = None
    quota_models = 0
    for m in models:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=m, contents=contents, config=cfg)
                if resp and resp.text:
                    return resp.text
                last_err = RuntimeError(f"Empty response from {m}")
                break
            except Exception as e:
                last_err = e
                err_msg = str(e)
                if attempt == 0 and ("503" in err_msg or "429" in err_msg or "ResourceExhausted" in err_msg or "temporary" in err_msg or "quota" in err_msg):
                    retry_wait = 5.0
                    m_delay = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg)
                    if m_delay:
                        retry_wait = min(float(m_delay.group(1)) + 1.0, 15.0)
                    logger.warning(f"Temporary issue or rate-limit on {m} ({e}), retrying in {retry_wait:.1f}s...")
                    time.sleep(retry_wait)
                    continue
                logger.warning(f"Gemini model {m} failed ({e}), trying next model...")
                break
        if last_err is not None and _is_quota_error(str(last_err)):
            quota_models += 1
    if last_err is not None and models and quota_models == len(models):
        raise GeminiQuotaExhausted(str(last_err)) from last_err
    raise last_err or RuntimeError("All Gemini models failed.")


def _chat_with_gemini(
    config: dict,
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    client, types = _get_genai_client_and_types(api_key)

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_msgs = [m for m in messages if m["role"] != "system"]
    prompt_content = "\n\n".join(m["content"] for m in user_msgs)

    cfg = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
        system_instruction=system,
    )
    return _generate_with_fallback(client, prompt_content, cfg, _gemini_models(config))


def _candidate_info(config: dict) -> str:
    cand = config.get("candidate", {})
    info = f"- Candidate: {cand.get('name', 'the candidate')}\n"
    if cand.get("profile"):
        info += f"- Profile: {cand['profile']}\n"
    if cand.get("seeking"):
        info += f"- Seeking: {cand['seeking']}\n"
    if cand.get("not_suitable"):
        info += f"- Not suitable: {cand['not_suitable']}\n"
    return info


# The whole description is sent: requirements usually follow the company blurb, past the
# old 2,000-char cut. Clean survivor descriptions measured ≤10,180 chars (2026-10-04);
# this bound only stops a runaway page (≈5k tokens) from eating the 250k-TPM budget.
MAX_DESCRIPTION_CHARS = 20_000


def _description(job: dict) -> str:
    return str(job.get("content", job.get("snippet", "")))[:MAX_DESCRIPTION_CHARS]


# Scoring rubric anchors for LLM evaluation (T48 / T24). Rule 4's exceptions and the removal of the
# "spread the scores" text come from the labelled comparison of 2026-10-04 (CHANGELOG, T48).
SCORING_RUBRIC = """SCORING RUBRIC & HARD ANCHORS (strictly enforce):
1. Location & Work Authorization Cap (score <= 30):
   If the job requires on-site presence outside India, or requires foreign citizenship / work authorization without visa sponsorship, cap score at <= 30. (India-based roles, India hybrid, or remote roles are eligible for higher scores).
2. Unsuitable Role Type Cap (score <= 40):
   If the role matches candidate's explicit 'Not suitable' criteria (e.g. pure frontend with zero backend, internship, non-technical management, IT support, or administering/configuring an enterprise platform such as Salesforce, Coupa, SAP or ServiceNow for a customer or internal business team), cap score at <= 40.
   Judge the work, not the employer's name: a software engineer building products or integrations at a company that makes such a platform (for example ServiceNow or Salesforce) is not platform administration.
3. Seniority Gap Cap (score <= 50):
   The candidate has ~3.3 years of experience. If the role strictly requires 6+ years of professional experience (Lead, Staff, Principal, Architect), cap score at <= 50. (Roles requiring 2-4 years are optimal; 4-5 years is acceptable up to 75-80 if stack matches).
4. Primary Stack Mismatch Cap (score <= 60):
   Apply this cap only if EVERY language or framework the posting accepts is outside the candidate's stack, i.e. it mandates C#/.NET Core, Java/Spring Boot, Go, C++, Ruby or similar and nothing else.
   Do NOT apply it when the posting lists Python, JavaScript, TypeScript or Node.js among its acceptable languages (the candidate's resume has Python), when it says "or another"/"any" object-oriented or programming language, or when it only prefers (does not require) a stack. For example "Java, Golang, or Python" is not a mismatch.
5. High Score Criteria (85-100):
   Award 85-100 ONLY when ALL three criteria hold:
   - Primary backend stack matches candidate's core stack (Node.js, TypeScript, Python, backend microservices, event-driven queues, databases/caching).
   - Experience target fits candidate's seniority (2-5 years / SDE-2 / Mid-level).
   - Location fits (India or Remote).
6. Moderate Match (65-84):
   Solid backend fit with minor stack or seniority stretch.
7. Too-Junior Cap (score <= 50):
   If the posting is aimed at freshers, new graduates or entry-level hires (it says fresher, new grad, graduate programme or campus hiring, or asks for 0-1 years), cap at <= 50. Judge by the experience the posting asks for, not by the title: an 'Associate' or 'Engineer I' role that asks for 2+ years (for example 3+) is NOT too junior."""


def score_job_with_gemini(job: dict, resume: str, config: dict, raise_on_error: bool = False) -> dict:
    """Score an individual job against a resume using Gemini.

    Returns:
        dict: {"score": <0-100>, "reason": "<one sentence explanation>"}
        On error, returns fallback: {"score": 0, "reason": "Scoring failed"},
        or re-raises when raise_on_error=True so callers can tell a failure
        apart from a genuine score of 0.
    """
    try:
        api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
        client, types = _get_genai_client_and_types(api_key)

        # The full resume is sent: ~4k chars is ~1k tokens, far below the TPM limit,
        # and truncating dropped Projects/Education from the scoring context.
        prompt = (
            "You are evaluating a job posting for a candidate. "
            "Output ONLY a JSON object with this exact format:\n"
            '{"score": <0-100>, "reason": "<one sentence explanation>"}\n\n'
            f"CANDIDATE PROFILE:\n{_candidate_info(config)}\n"
            f"RESUME:\n{resume}\n\n"
            f"JOB:\n"
            f"Company: {job.get('company', '')}\n"
            f"Title: {job.get('title', '')}\n"
            f"Location: {job.get('location', '')}\n"
            f"Description:\n{_description(job)}\n\n"
            f"{SCORING_RUBRIC}\n"
        )

        cfg = types.GenerateContentConfig(
            temperature=float(config.get("gemini_temperature", 0.1)),
            response_mime_type="application/json",
        )
        raw_text = _generate_with_fallback(client, prompt, cfg, _gemini_models(config))
        start, end = raw_text.find("{"), raw_text.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError(f"No JSON object in response: {raw_text[:100]}")
        data = json.loads(raw_text[start:end])
        if not isinstance(data, dict) or "score" not in data or "reason" not in data:
            raise ValueError(f"Missing score or reason keys in JSON: {data}")
        return {
            "score": int(data["score"]),
            "reason": str(data["reason"]),
        }
    except Exception as e:
        logger.error(f"Gemini scoring error: {e}")
        if raise_on_error:
            raise
        return {"score": 0, "reason": "Scoring failed"}


# --- Structured scoring (T41): the model extracts facts and sub-scores, code decides the score ---------
# Prompt wording moved calibration, not ranking (T48), and one run per job flips ambiguous postings by ~50
# points (T60). Here the model answers narrow questions (years asked? stack accepted? onsite abroad?) and the
# caps are applied deterministically; the weighted mean gives distinct values where one score used to tie.
SUBSCORE_WEIGHTS = {"stack_fit": 0.35, "role_fit": 0.25, "seniority_fit": 0.25, "location_fit": 0.15}

STRUCTURED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "stack_fit": {"type": "integer", "minimum": 0, "maximum": 100},
        "role_fit": {"type": "integer", "minimum": 0, "maximum": 100},
        "seniority_fit": {"type": "integer", "minimum": 0, "maximum": 100},
        "location_fit": {"type": "integer", "minimum": 0, "maximum": 100},
        "min_years": {"type": "integer"},
        "accepts_candidate_stack": {"type": "boolean"},
        "onsite_outside_india": {"type": "boolean"},
        "aimed_at_freshers": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["stack_fit", "role_fit", "seniority_fit", "location_fit", "min_years",
                 "accepts_candidate_stack", "onsite_outside_india", "aimed_at_freshers", "reason"],
}


def combine_subscores(f: dict) -> dict:
    """Weighted mean of the sub-scores, then the hard caps. Returns the score and which cap (if any) bit."""
    score = round(sum(float(f[k]) * w for k, w in SUBSCORE_WEIGHTS.items()))
    caps: list[tuple[int, str]] = []
    if f.get("onsite_outside_india"):
        caps.append((30, "onsite or work authorisation outside India"))
    if f["role_fit"] < 30:
        caps.append((40, "role type not suitable"))
    years = f.get("min_years")
    if years is not None and years >= 6:
        caps.append((50, "asks for 6+ years"))
    if f.get("aimed_at_freshers"):
        caps.append((50, "aimed at freshers"))
    if not f.get("accepts_candidate_stack", True):
        caps.append((60, "every accepted stack is outside the candidate's"))
    capped_by = ""
    for cap, why in sorted(caps):
        if score > cap:
            score, capped_by = cap, why
        break  # only the lowest cap can matter
    return {"score": int(score), "capped_by": capped_by}


STRUCTURED_INSTRUCTIONS = """You are extracting facts about a job posting and rating how well it fits a candidate.
Output ONLY a JSON object that follows the schema. Do NOT compute an overall score: the caller does that.

Fields:
- stack_fit (0-100): how well the languages/frameworks the posting requires or accepts match the candidate's stack (100 = the candidate's own stack or any language; 50 = partly; 0 = a mandatory stack the candidate does not have).
- role_fit (0-100): how well the kind of work matches what the candidate seeks. 80-100 backend or full-stack software engineering; 0-30 pure frontend, internship, non-technical management, IT support, QA, or administering/configuring an enterprise platform (Salesforce, SAP, ServiceNow, Coupa, Workday...). Judge the work, not the employer's name: a software engineer building products at a company that makes such a platform is not platform administration.
- seniority_fit (0-100): 100 when the posting asks for about 2-5 years; 60-80 for 5-6; 30-50 when it asks for 6+ years or is aimed at freshers; 0-30 for staff/principal/lead.
- location_fit (0-100): 100 for India or remote open to India; low only when the job is outside India.
- min_years: the LOWEST number of years of professional experience the posting asks for ("3-5 years" -> 3, "6+ years" -> 6); -1 if it states none.
- accepts_candidate_stack: true if the posting accepts at least one of the candidate's languages (Node.js, TypeScript, JavaScript, Python), or says "any"/"another" language, or does not mandate a stack; false only if EVERY language or framework it requires or accepts is outside them (C#/.NET, Java/Spring Boot, Go, C++, Ruby, PHP, Rust...).
- onsite_outside_india: true if the job requires on-site presence outside India, or citizenship / work authorisation outside India without sponsorship.
- aimed_at_freshers: true if the posting is aimed at freshers, new graduates or entry-level hires (0-1 years).
- reason: one sentence."""


def score_job_structured_with_gemini(job: dict, resume: str, config: dict) -> dict:
    """Score one job by extracting facts and sub-scores (see combine_subscores).

    Returns {"score", "reason", "capped_by", "stack_fit", "role_fit", "seniority_fit", "location_fit",
    "min_years" (None if not stated), ...}. Raises on any failure so the caller can retry the job later.
    """
    api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    client, types = _get_genai_client_and_types(api_key)
    prompt = (
        f"{STRUCTURED_INSTRUCTIONS}\n\n"
        f"CANDIDATE PROFILE:\n{_candidate_info(config)}\n"
        f"RESUME:\n{resume}\n\n"
        f"JOB:\n"
        f"Company: {job.get('company', '')}\n"
        f"Title: {job.get('title', '')}\n"
        f"Location: {job.get('location', '')}\n"
        f"Description:\n{_description(job)}\n"
    )
    cfg = types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json",
                                      response_json_schema=STRUCTURED_SCHEMA)
    raw = _generate_with_fallback(client, prompt, cfg, _gemini_models(config))
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got: {raw[:100]}")
    missing = [k for k in STRUCTURED_SCHEMA["required"] if k not in data]
    if missing:
        raise ValueError(f"Structured scoring output lacks {missing}")
    facts: dict[str, Any] = {k: max(0, min(100, int(data[k]))) for k in SUBSCORE_WEIGHTS}
    years = int(data["min_years"])
    facts.update(
        min_years=years if years >= 0 else None,
        accepts_candidate_stack=bool(data["accepts_candidate_stack"]),
        onsite_outside_india=bool(data["onsite_outside_india"]),
        aimed_at_freshers=bool(data["aimed_at_freshers"]),
        reason=str(data["reason"]),
    )
    return {**facts, **combine_subscores(facts)}


BATCH_SCORE_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "reason": {"type": "string"},
        },
        "required": ["job_id", "score", "reason"],
    },
}


def score_jobs_batch_with_gemini(jobs: list[dict], resume: str, config: dict) -> dict[str, dict]:
    """Score several jobs in ONE Gemini call with a structured JSON schema.

    Each job dict needs a unique "id". Returns {id: {"score", "reason"}} for every id
    the model answered; ids it skipped are simply absent (callers retry them later).
    Raises if the call fails or the output is not a JSON array.
    """
    api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    client, types = _get_genai_client_and_types(api_key)

    jobs_text = "\n\n".join(
        f"JOB_ID: {j['id']}\n"
        f"Company: {j.get('company', '')}\n"
        f"Title: {j.get('title', '')}\n"
        f"Location: {j.get('location', '')}\n"
        f"Description:\n{_description(j)}"
        for j in jobs
    )
    prompt = (
        "You are evaluating job postings for a candidate. Score EACH job independently "
        "against the candidate (do not rank the jobs against each other).\n"
        "Return a JSON array with exactly one object per JOB_ID: "
        '{"job_id": "<JOB_ID>", "score": <0-100>, "reason": "<one sentence explanation>"}.\n\n'
        f"CANDIDATE PROFILE:\n{_candidate_info(config)}\n"
        f"RESUME:\n{resume}\n\n"
        f"JOBS:\n{jobs_text}\n\n"
        f"{SCORING_RUBRIC}\n"
    )
    cfg = types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
        response_json_schema=BATCH_SCORE_SCHEMA,
    )
    raw_text = _generate_with_fallback(client, prompt, cfg, _gemini_models(config))
    data = json.loads(raw_text)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got: {raw_text[:100]}")

    wanted = {str(j["id"]) for j in jobs}
    out: dict[str, dict] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        jid = str(item.get("job_id", ""))
        if jid in wanted and "score" in item:
            out[jid] = {
                "score": max(0, min(100, int(item["score"]))),
                "reason": str(item.get("reason", "")),
            }
    return out


def chat_with_llm(
    config: dict,
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    provider = config.get("llm_provider")
    if provider == "gemini":
        return _chat_with_gemini(config, messages, temperature, max_tokens)
    if provider == "anthropic":
        return _chat_with_anthropic(config, messages, temperature, max_tokens)
    if provider == "claude_cli":
        return _chat_with_claude_cli(config, messages, temperature, max_tokens)
    global _openrouter_deprecation_warned
    if not _openrouter_deprecation_warned:
        logger.warning("llm_provider=openrouter is deprecated — set llm_provider=gemini in config.json")
        _openrouter_deprecation_warned = True
    return chat_with_fallback(_make_openrouter_client(config), config, messages, temperature, max_tokens)


def chat_with_fallback(
    llm: OpenAI,
    config: dict,
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    primary = config.get("openrouter_model", "nvidia/nemotron-3-super-120b-a12b:free")
    fallbacks = config.get("openrouter_fallback_models", [])
    models = [primary] + [m for m in fallbacks if m != primary]

    for model_idx, model in enumerate(models):
        label = f"[model {model_idx + 1}/{len(models)}] {model}"
        for attempt in range(2):
            try:
                logger.debug(f"LLM call → {label} (attempt {attempt + 1})")
                t0 = time.time()
                resp = llm.chat.completions.create(
                    model=model,
                    messages=cast("Any", messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed = time.time() - t0
                text = resp.choices[0].message.content or ""
                usage = resp.usage
                if usage:
                    logger.debug(
                        f"LLM response: {len(text)} chars in {elapsed:.1f}s "
                        f"(in={usage.prompt_tokens} out={usage.completion_tokens} tokens) via {model}"
                    )
                else:
                    logger.debug(f"LLM response: {len(text)} chars in {elapsed:.1f}s via {model}")
                return text
            except RateLimitError:
                if attempt == 0:
                    logger.warning(f"Rate-limited on {model} — retrying in 3s...")
                    time.sleep(3)
                    continue
                logger.warning(f"Rate-limited on {model} (quota exhausted) — trying next model...")
                break
            except Exception as e:
                logger.error(f"LLM error ({model}): {e}")
                break

    raise RuntimeError("All LLM models failed. Check your OpenRouter API key and quota.")

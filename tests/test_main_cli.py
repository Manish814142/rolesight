"""CLI dispatch + export/config helpers. No API keys, no network."""
import json

import pytest

from job_hunt import main


def _argv(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["autopilot", *args])


def test_help_exits_zero(monkeypatch, capsys):
    _argv(monkeypatch)
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == 0


def test_init_dispatch(monkeypatch):
    called = {}
    monkeypatch.setattr(main, "init_project", lambda: called.setdefault("ok", True))
    _argv(monkeypatch, "init")
    main.main()
    assert called["ok"]


def test_scan_dispatch(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: {"c": 1})
    monkeypatch.setattr(main, "load_companies", lambda: ["co"])
    ran = {}
    monkeypatch.setattr("job_hunt.scanner.run_scan", lambda cfg, co: ran.update(cfg=cfg, co=co))
    _argv(monkeypatch, "scan")
    main.main()
    assert ran["cfg"] == {"c": 1} and ran["co"] == ["co"]


def test_draft_dispatch(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: {})
    got = {}
    monkeypatch.setattr("job_hunt.drafter.draft_application", lambda cfg, ref, jd_file=None: got.update(ref=ref, jd=jd_file))
    _argv(monkeypatch, "draft", "#3")
    main.main()
    assert got == {"ref": "#3", "jd": None}


def test_draft_passes_jd_file(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: {})
    got = {}
    monkeypatch.setattr("job_hunt.drafter.draft_application", lambda cfg, ref, jd_file=None: got.update(ref=ref, jd=jd_file))
    _argv(monkeypatch, "draft", "https://x.co/j/1", "--jd-file", "jd.txt")
    main.main()
    assert got == {"ref": "https://x.co/j/1", "jd": "jd.txt"}


def test_draft_jd_file_needs_a_path(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: {})
    _argv(monkeypatch, "draft", "https://x.co/j/1", "--jd-file")
    with pytest.raises(SystemExit):
        main.main()


def test_draft_requires_arg(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: {})
    _argv(monkeypatch, "draft")
    with pytest.raises(SystemExit):
        main.main()


def test_export_dispatch(monkeypatch):
    got = {}
    monkeypatch.setattr(main, "export_jobs", lambda min_score, days: got.update(m=min_score, d=days))
    _argv(monkeypatch, "export", "--min", "70", "--days", "7")
    main.main()
    assert got == {"m": 70, "d": 7}


def test_unknown_command(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: {})
    _argv(monkeypatch, "frobnicate")
    with pytest.raises(SystemExit):
        main.main()


# --- _parse_export_args --------------------------------------------------------

def test_parse_export_args_defaults():
    assert main._parse_export_args(["autopilot", "export"]) == (0, 0)


def test_parse_export_args_bad_min():
    with pytest.raises(SystemExit):
        main._parse_export_args(["autopilot", "export", "--min", "abc"])


def test_parse_export_args_bad_days():
    with pytest.raises(SystemExit):
        main._parse_export_args(["autopilot", "export", "--days"])


# --- export_jobs ---------------------------------------------------------------

def test_export_jobs_no_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main.export_jobs()


def test_export_jobs_from_last_scan(tmp_path, monkeypatch, capsys):
    """export reads the last finished scan from data/jobs.db (T32)."""
    from job_hunt.db import finish_scan, init_db, save_job, start_scan, update_job_status
    from job_hunt.models import JobPosting, job_key
    monkeypatch.chdir(tmp_path)
    init_db("data/jobs.db")
    sid = start_scan()
    for company, url, score in (("Acme", "u", 90), ("Beta", "v", 30)):
        j = JobPosting(global_id=url, ats="greenhouse", company=company, title="SWE", location="Pune", is_remote=False,
                       url=url)
        save_job(j)
        update_job_status(job_key(j), "scored", score, "r")
    finish_scan(sid)
    main.export_jobs(min_score=50)
    out = capsys.readouterr().out
    assert "Exported 1 jobs" in out


def test_export_jobs_days_no_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main.export_jobs(days=7)


# --- load_config / load_companies ---------------------------------------------

def test_load_companies_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main.load_companies()


def test_load_config_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main.load_config()


def test_load_config_env_override(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_api_key": "sk-config"}))
    monkeypatch.setenv("GEMINI_API_KEY", "sk-env-real")
    cfg = main.load_config()
    assert cfg["gemini_api_key"] == "sk-env-real"


def test_load_config_placeholder_does_not_clobber(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_api_key": "sk-config-real"}))
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    cfg = main.load_config()
    assert cfg["gemini_api_key"] == "sk-config-real"


def test_load_config_telegram_and_candidate_env(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_api_key": "sk-real"}))
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("CANDIDATE_NAME", "Ada")
    monkeypatch.setenv("MIN_SCORE", "70")
    monkeypatch.setenv("TOP_N", "3")
    cfg = main.load_config()
    assert cfg["telegram"] == {"token": "tok", "chat_id": "42"}
    assert cfg["candidate"]["name"] == "Ada"
    assert cfg["candidate"]["min_score"] == 70 and cfg["candidate"]["top_n"] == 3


def test_load_config_without_any_api_key_does_not_exit(tmp_path, monkeypatch, clean_env):
    """A config with no keys loads (doctor and export need none); scoring fails later with a clear message."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"name": "x"}))
    cfg = main.load_config()
    assert not cfg.get("gemini_api_key") and cfg["llm_provider"] == "gemini"


def test_removed_providers_keys_are_ignored(tmp_path, monkeypatch, clean_env):
    """TinyFish and OpenRouter were removed (T42): their env vars no longer reach the config."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({}))
    monkeypatch.setenv("TINYFISH_API_KEY", "sk-x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-y")
    cfg = main.load_config()
    assert "tinyfish_api_key" not in cfg and "openrouter_api_key" not in cfg


def test_load_config_defaults_provider_to_gemini(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({}))
    assert main.load_config()["llm_provider"] == "gemini"


def test_load_config_drops_placeholder_telegram_values(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps(
        {"telegram": {"token": "YOUR_TELEGRAM_BOT_TOKEN", "chat_id": "YOUR_TELEGRAM_CHAT_ID"}}))
    cfg = main.load_config()
    assert not cfg["telegram"].get("token")
    assert not cfg["telegram"].get("chat_id")


def test_load_config_accepts_telegram_bot_token_alias(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({}))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    cfg = main.load_config()
    assert cfg["telegram"] == {"token": "123:abc", "chat_id": "42"}


def test_export_jobs_days_with_history(tmp_path, monkeypatch, capsys):
    """export --days reads every job scored in the window from data/jobs.db (T32)."""
    from job_hunt.db import init_db, save_job, update_job_status
    from job_hunt.models import JobPosting, job_key
    monkeypatch.chdir(tmp_path)
    init_db("data/jobs.db")
    j = JobPosting(global_id="u", ats="greenhouse", company="Acme", title="MLE", location="Pune", is_remote=False, url="u")
    save_job(j)
    update_job_status(job_key(j), "scored", 90, "r")
    main.export_jobs(days=7)
    assert "Exported 1 jobs" in capsys.readouterr().out


def test_init_project_scaffolds(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main.init_project()
    assert (tmp_path / "companies.json").exists()
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / ".env").exists()
    assert (tmp_path / "resume" / "YOUR_RESUME.md").exists()
    assert (tmp_path / "output").is_dir() and not (tmp_path / "state").exists()   # state/ is retired (T34, T83)
    # idempotent — second run skips without error
    main.init_project()
    assert "already exists" in capsys.readouterr().out


def test_harvest_dispatch(monkeypatch):
    called = {}
    monkeypatch.setattr("job_hunt.harvester.main", lambda args: called.setdefault("ok", True))
    _argv(monkeypatch, "harvest")
    main.main()
    assert called["ok"]


def test_main_module_run(monkeypatch):
    import runpy
    called = {}
    monkeypatch.setattr(main, "main", lambda: called.setdefault("ok", True))
    runpy.run_module("job_hunt.__main__", run_name="__main__")
    assert called["ok"]



def test_discover_command_dispatches_without_config(tmp_path, monkeypatch):
    """discover needs no API keys, so it must run before load_config()."""
    monkeypatch.chdir(tmp_path)
    seen = {}
    import job_hunt.discovery as discovery
    monkeypatch.setattr(discovery, "main", lambda argv: seen.setdefault("argv", argv))
    monkeypatch.setattr(main.sys, "argv", ["autopilot", "discover", "--seeds", "s.txt"])
    main.main()
    assert seen["argv"] == ["--seeds", "s.txt"]


def test_scan_posted_within_flag_sets_config(tmp_path, monkeypatch, clean_env):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {"name": "x"}}))
    (tmp_path / "companies.json").write_text("[]")
    seen = {}
    import job_hunt.scanner as scanner_mod
    monkeypatch.setattr(scanner_mod, "run_scan", lambda cfg, comps: seen.setdefault("cfg", cfg))
    monkeypatch.setattr(main.sys, "argv", ["autopilot", "scan", "--posted-within", "3"])
    main.main()
    assert seen["cfg"]["candidate"]["max_posted_age_days"] == 3

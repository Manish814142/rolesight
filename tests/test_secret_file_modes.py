"""T105: the files that hold keys are readable by their owner only.

`init` wrote `.env` and `config.json` with the umask (664 here: group-writable, world-readable), and `init --resume` can save
the Gemini key into `.env`. `doctor` now also says when an existing key file is readable by others.
"""
import os
import stat

import pytest

from job_hunt import doctor, onboarding

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
FAKE_KEY = "AIza" + "-mode-test-0123456789"          # built at run time (see tests/test_public_release.py)


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def loose_umask():
    old = os.umask(0o002)                             # what this machine uses: files come out 664
    yield
    os.umask(old)


def test_init_creates_the_key_files_readable_by_their_owner_only(tmp_path, monkeypatch, loose_umask):
    monkeypatch.chdir(tmp_path)
    onboarding._scaffold(tmp_path)
    assert _mode(tmp_path / ".env") == 0o600
    assert _mode(tmp_path / "config.json") == 0o600
    assert _mode(tmp_path / "companies.json") == 0o664          # not a secret: left to the umask


def test_saving_a_typed_key_tightens_an_existing_env(tmp_path, monkeypatch, loose_umask):
    env = tmp_path / ".env"
    env.write_text('GEMINI_API_KEY="your_gemini_api_key_here"\n')
    os.chmod(env, 0o664)
    monkeypatch.setattr(onboarding.sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(onboarding.getpass, "getpass", lambda prompt: FAKE_KEY)
    assert onboarding._api_key(tmp_path) == FAKE_KEY
    assert _mode(env) == 0o600


def test_doctor_warns_about_a_key_file_others_can_read(tmp_path):
    env, cfg = tmp_path / ".env", tmp_path / "config.json"
    env.write_text(f'GEMINI_API_KEY="{FAKE_KEY}"\n')
    cfg.write_text('{"gemini_api_key": "YOUR_GEMINI_API_KEY"}')
    os.chmod(env, 0o664)
    os.chmod(cfg, 0o664)
    warnings = doctor.check_secret_file_modes(tmp_path)
    assert warnings == [".env holds a key and other users can read it (mode 664): run chmod 600 .env"]   # config: placeholder only
    os.chmod(env, 0o600)
    assert doctor.check_secret_file_modes(tmp_path) == []


@pytest.mark.parametrize("mode", [0o640, 0o604, 0o644, 0o664, 0o666])
def test_doctor_warns_when_the_group_or_anyone_else_can_read_the_key_file(tmp_path, mode):
    """Found in review (a mutant that looked only at "others" survived): a group-readable file counts too."""
    (tmp_path / ".env").write_text(f'GEMINI_API_KEY="{FAKE_KEY}"\n')
    os.chmod(tmp_path / ".env", mode)
    assert len(doctor.check_secret_file_modes(tmp_path)) == 1


@pytest.mark.parametrize("mode", [0o600, 0o400])
def test_doctor_is_quiet_about_a_key_file_only_its_owner_can_read(tmp_path, mode):
    (tmp_path / ".env").write_text(f'GEMINI_API_KEY="{FAKE_KEY}"\n')
    os.chmod(tmp_path / ".env", mode)
    assert doctor.check_secret_file_modes(tmp_path) == []


def test_doctor_prints_the_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f'TELEGRAM_TOKEN="{FAKE_KEY}"\n')
    os.chmod(tmp_path / ".env", 0o644)
    monkeypatch.setattr(doctor, "check_sqlite_write", lambda p="x": (True, "OK"))
    monkeypatch.setattr(doctor, "check_gemini_quota", lambda *a, **k: (True, "OK"))
    monkeypatch.setattr(doctor, "check_telegram_credentials", lambda *a, **k: (False, "off"))
    monkeypatch.setattr(doctor, "check_ats_egress", lambda: {})
    doctor.run_doctor(db_path=str(tmp_path / "x.db"), env_path=str(tmp_path / ".env"))
    assert "[WARN] Key file: .env holds a key and other users can read it (mode 644)" in capsys.readouterr().out

"""T15: the log file's location is configurable, and the test suite never writes to the repo's own log."""
import logging
from pathlib import Path

from job_hunt import log


def _file_handlers(logger: logging.Logger) -> list:
    return [h for h in logger.handlers if isinstance(h, logging.FileHandler)]


def test_log_file_follows_the_env_var(tmp_path, monkeypatch):
    target = tmp_path / "custom.log"
    monkeypatch.setenv("JOBNOTIFY_LOG", str(target))
    logger = log.get_logger("autopilot-test-env-var")
    try:
        logger.info("hello from the test")
        for h in logger.handlers:
            h.flush()
        assert "hello from the test" in target.read_text()
    finally:
        for h in list(logger.handlers):
            h.close()
            logger.removeHandler(h)


def test_the_suite_does_not_log_into_the_repo():
    """conftest points JOBNOTIFY_LOG at a temp dir before job_hunt is imported; the real consumer is the live logger."""
    handlers = _file_handlers(log.get_logger())
    assert handlers, "the autopilot logger should have a file handler"
    repo_log = Path("scan.log").resolve()
    assert all(Path(h.baseFilename).resolve() != repo_log for h in handlers)
    assert all(Path.cwd().resolve() not in Path(h.baseFilename).resolve().parents for h in handlers)


# --- T16: location, rotation, module loggers ---------------------------------------

def test_default_log_is_data_autopilot_log(monkeypatch):
    monkeypatch.delenv("JOBNOTIFY_LOG", raising=False)
    assert log.log_path() == Path("data/autopilot.log")


def test_a_missing_data_dir_is_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JOBNOTIFY_LOG", raising=False)
    logger = log.get_logger("autopilot-test-mkdir")
    try:
        logger.info("first line")
        assert "first line" in (tmp_path / "data" / "autopilot.log").read_text()
        assert not (tmp_path / "scan.log").exists()
    finally:
        for h in list(logger.handlers):
            h.close()
            logger.removeHandler(h)


def test_the_log_rotates_at_the_size_limit(tmp_path, monkeypatch):
    target = tmp_path / "rot.log"
    monkeypatch.setenv("JOBNOTIFY_LOG", str(target))
    monkeypatch.setattr(log, "MAX_LOG_BYTES", 2_000)
    logger = log.get_logger("autopilot-test-rotation")
    try:
        for i in range(200):
            logger.debug(f"line {i:04d} " + "x" * 40)
        files = sorted(p.name for p in tmp_path.iterdir())
        assert files == ["rot.log", "rot.log.1", "rot.log.2", "rot.log.3"]       # 3 backups, no more
        assert target.stat().st_size <= 2_000
        assert "line 0199" in target.read_text()                                  # newest lines stay in the live file
    finally:
        for h in list(logger.handlers):
            h.close()
            logger.removeHandler(h)


def test_the_default_limits_are_5mb_times_3():
    assert (log.MAX_LOG_BYTES, log.LOG_BACKUPS) == (5_000_000, 3)


def test_warnings_from_module_loggers_reach_the_log_file_and_the_console():
    """adapters/scorer use logging.getLogger(__name__), not the autopilot logger; their warnings were lost from the file."""
    log.get_logger()
    pkg = logging.getLogger("job_hunt")
    files = _file_handlers(pkg)
    assert files and any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
                         for h in pkg.handlers), "warnings must still reach the console"
    logging.getLogger("job_hunt.adapters.greenhouse").warning("greenhouse fetch failed for acme: boom")
    for h in files:
        h.flush()
    assert "greenhouse fetch failed for acme: boom" in Path(files[0].baseFilename).read_text()

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

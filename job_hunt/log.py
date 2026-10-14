
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH_ENV = "ROLESIGHT_LOG"
MAX_LOG_BYTES = 5_000_000
LOG_BACKUPS = 3


def redact(text: str, *secrets: str | None) -> str:
    """`text` with each secret replaced by ***, so an error message can be printed or logged (T92, T95).

    Secrets shorter than 8 characters are left alone: replacing "a" would wreck the message and protects nothing.
    Redact the whole text, then cut it: a secret cut in half no longer matches and its first part would be printed."""
    for secret in secrets:
        if secret and len(secret) >= 8:
            text = text.replace(secret, "***")
    return text


def log_path() -> Path:
    """Where the DEBUG log goes: $ROLESIGHT_LOG, else data/autopilot.log (the test suite sets the variable)."""
    return Path(os.getenv(LOG_PATH_ENV) or "data/autopilot.log")


def _build_handlers() -> list[logging.Handler]:
    fmt = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console level is INFO by default; set LOG_LEVEL=DEBUG for full per-URL/per-job
    # detail on stdout (the log file always captures DEBUG regardless).
    console_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(fmt)
    handlers: list[logging.Handler] = [console]

    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        handlers.append(file_handler)
    except OSError:
        pass
    return handlers


def get_logger(name: str = "autopilot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handlers = _build_handlers()
    for handler in handlers:
        logger.addHandler(handler)

    # The adapters, scorer and other modules log through logging.getLogger(__name__) ("job_hunt.*"), not
    # through this logger. Give them the same handlers: otherwise their warnings (e.g. "fetch failed for
    # <slug>") never reach the log file, and a handler-less logger would print bare text to stderr.
    if name == "autopilot":
        package = logging.getLogger("job_hunt")
        if not package.handlers:
            package.setLevel(logging.DEBUG)
            for handler in handlers:
                package.addHandler(handler)

    return logger

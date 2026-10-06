import logging
import os
import sys
from pathlib import Path

LOG_PATH_ENV = "JOBNOTIFY_LOG"


def log_path() -> Path:
    """Where the DEBUG log goes: $JOBNOTIFY_LOG, else ./scan.log (the test suite sets the variable)."""
    return Path(os.getenv(LOG_PATH_ENV) or "scan.log")


def get_logger(name: str = "autopilot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console level is INFO by default; set LOG_LEVEL=DEBUG for full per-URL/per-job
    # detail on stdout (the scan.log file always captures DEBUG regardless).
    console_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    try:
        file_handler = logging.FileHandler(log_path(), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        pass

    return logger

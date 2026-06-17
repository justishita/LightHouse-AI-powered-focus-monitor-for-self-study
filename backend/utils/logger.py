"""
utils/logger.py — Centralized logging setup.

Why centralized: detection events, alerts, and blocker actions all need
consistent timestamps and a single log file so you can correlate "phone
detected at 14:32:01" with "alert fired at 14:32:01" later, instead of
each module configuring its own ad-hoc print statements.
"""

import logging
from logging.handlers import RotatingFileHandler

from config import settings

_configured = False  # guards against re-adding handlers on uvicorn --reload


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Rotating so a long-running dev session doesn't grow the log file
    # unboundedly — 1MB per file, keep 3 backups, plenty for local dev.
    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Call this at the top of any module: logger = get_logger(__name__)"""
    _configure_root_logger()
    return logging.getLogger(name)

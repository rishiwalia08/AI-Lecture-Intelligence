"""
src/utils/logger.py
-------------------
Centralised logging configuration for the Speech RAG Phase 1 pipeline.

Usage
-----
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Processing started")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "pipeline.log"
DEFAULT_LOG_LEVEL = logging.INFO

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Internal registry so we don't add duplicate handlers
_configured_loggers: set[str] = set()


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
def get_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = DEFAULT_LOG_LEVEL,
) -> logging.Logger:
    """
    Return a named logger with both console and file handlers.

    Parameters
    ----------
    name : str
        Logger name, typically ``__name__`` of the calling module.
    log_file : Path, optional
        Path to the log file. Defaults to ``logs/pipeline.log``
        relative to the project root.
    level : int
        Logging level (e.g. ``logging.DEBUG``). Defaults to INFO.

    Returns
    -------
    logging.Logger
    """
    if name in _configured_loggers:
        return logging.getLogger(name)

    log_file = log_file or DEFAULT_LOG_FILE
    _ensure_log_dir(log_file)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler
    _add_handler(
        logger,
        logging.StreamHandler(sys.stdout),
        formatter,
        level,
    )

    # File handler
    _add_handler(
        logger,
        logging.FileHandler(log_file, encoding="utf-8"),
        formatter,
        level,
    )

    logger.propagate = False  # avoid double-logging to root
    _configured_loggers.add(name)
    return logger


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _ensure_log_dir(log_file: Path) -> None:
    """Create log directory if it doesn't exist."""
    log_file.parent.mkdir(parents=True, exist_ok=True)


def _add_handler(
    logger: logging.Logger,
    handler: logging.Handler,
    formatter: logging.Formatter,
    level: int,
) -> None:
    """Attach a formatted handler to a logger."""
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

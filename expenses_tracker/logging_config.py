"""Structured logging configuration with file rotation and severity control.

Usage:
    from expenses_tracker.logging_config import configure_logging, get_logger
    configure_logging(level="INFO", log_dir="logs")
    logger = get_logger("expenses_tracker.gui")
    logger.info("Application started")
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIR = "logs"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 5


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.pathname}:{record.lineno}",
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Merge any extra fields passed via `extra={...}`
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
            }:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Simple colored formatter for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with ANSI color codes."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


def configure_logging(
    level: str = "INFO",
    log_dir: str = DEFAULT_LOG_DIR,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    json_format: bool = True,
    console: bool = True,
) -> None:
    """Set up root logger with rotating file handler and optional console handler.

    Args:
        level: Minimum severity (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files (created if missing).
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated files to keep.
        json_format: If True, file output is JSONLines; otherwise plain text.
        console: If True, also emit formatted logs to stdout.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid adding duplicate handlers on repeated calls
    if root_logger.handlers:
        return

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    if json_format:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root_logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            ColoredConsoleFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given dotted name."""
    return logging.getLogger(name)

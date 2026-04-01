"""
Centralized logging configuration for FinBot API.

Production pattern: JSON-structured logs for machine parsing (Datadog, CloudWatch, etc.)
Local dev: Human-readable coloured logs.

Usage:
    from app.core.logging_config import setup_logging
    setup_logging()  # Call once at startup

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Server started", extra={"port": 8000})
"""

import logging
import logging.config
import json
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.
    This is what Datadog/CloudWatch/ELK/Splunk expect.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Merge any 'extra' fields passed via logger.info(..., extra={...})
        # This is how you add request_id, user_id, latency, etc.
        for key in ("request_id", "user_id", "thread_id", "latency_ms",
                     "status_code", "method", "path", "attempt", "error"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    """
    Human-readable coloured formatter for local development.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Build extra context string from common fields
        extras = []
        for key in ("request_id", "user_id", "thread_id", "latency_ms",
                     "status_code", "method", "path", "attempt", "error"):
            value = getattr(record, key, None)
            if value is not None:
                extras.append(f"{key}={value}")
        extra_str = f" | {', '.join(extras)}" if extras else ""

        msg = (
            f"{color}{timestamp} [{record.levelname:<7}]{self.RESET} "
            f"{record.name}: {record.getMessage()}{extra_str}"
        )

        if record.exc_info and record.exc_info[0] is not None:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(log_level: str = "INFO", environment: str = "production"):
    """
    Configure logging for the entire application.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL
        environment: "production" for JSON logs, anything else for dev format
    """
    # Determine formatter based on environment
    is_production = environment.lower() == "production"

    # Build config dict
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "dev": {
                "()": DevFormatter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json" if is_production else "dev",
            },
        },
        "root": {
            "level": log_level.upper(),
            "handlers": ["console"],
        },
        # Quiet down noisy third-party libraries
        "loggers": {
            "uvicorn": {"level": "INFO"},
            "uvicorn.access": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "langchain": {"level": "WARNING"},
            "langgraph": {"level": "WARNING"},
            "psycopg.pool": {"level": "WARNING"},
        },
    }

    logging.config.dictConfig(config)

    logger = logging.getLogger("finbot")
    logger.info(
        "Logging initialized",
        extra={"environment": environment, "level": log_level} if not is_production else {},
    )

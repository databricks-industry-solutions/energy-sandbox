"""Structured logging helpers (stdlib logging with JSON-friendly extras)."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Mapping, Optional


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "structured", None)
        if isinstance(extra, Mapping):
            payload.update({str(k): v for k, v in extra.items()})
        return json.dumps(payload, default=str)


def setup_logging(
    level: int = logging.INFO,
    *,
    json_logs: bool = False,
) -> None:
    """
    Configure logging for the ``connector`` logger tree only.

    On Databricks, replacing **root** handlers breaks notebook output capture and can trigger
    “Failed to upload command result to DBFS” / 403-style failures.
    """
    log = logging.getLogger("connector")
    log.handlers.clear()
    log.setLevel(level)
    log.propagate = True
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
        )
    log.addHandler(handler)
    if not os.environ.get("DATABRICKS_RUNTIME_VERSION"):
        root = logging.getLogger()
        if not root.handlers:
            root.addHandler(logging.StreamHandler(sys.stdout))
            root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_extra(**kwargs: Any) -> dict[str, Any]:
    """Attach to LogRecord via ``logger.info(..., extra={'structured': log_extra(...)})``."""
    return {"structured": kwargs}

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Merge any extras passed via the `extra` kwarg
        for key in ("method", "path", "status_code", "duration_ms", "client_ip"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure structured JSON logging for the application."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

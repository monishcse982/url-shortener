import json
import logging
from datetime import UTC, datetime
from logging.config import dictConfig
from typing import Any

from asgi_correlation_id import CorrelationIdFilter

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            # 2. Extract the correlation ID attached by the filter
            # It will be None if a log happens outside an HTTP request context
            "correlation_id": getattr(record, "correlation_id", None),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        return json.dumps(log)


def setup_logging() -> None:
    log_level = settings.log_level.upper()

    formatter_name = "json" if settings.log_format == "json" else "plain"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            # 3. Define the filter in the logging dictionary
            "filters": {
                "correlation_id": {
                    "()": CorrelationIdFilter,
                    "uuid_length": 32,
                },
            },
            "formatters": {
                "plain": {
                    # 4. Add %(correlation_id)s to your plain text layout
                    "format": "%(asctime)s [%(levelname)s] [%(correlation_id)s]"
                    "%(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "json": {
                    "()": JsonFormatter,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_name,
                    "stream": "ext://sys.stdout",
                    # 5. Attach the filter to your console handler
                    "filters": ["correlation_id"],
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                    "filters": ["correlation_id"],
                },
            },
        }
    )

"""Structured logging configuration for Cloud Logging-compatible output."""

import logging
import sys


class ExecutionIdFilter(logging.Filter):
    """Ensure third-party log records also have an execution ID."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "execution_id"):
            record.execution_id = "-"
        return True


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure a consistent process-wide logger and return the app logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ExecutionIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "execution_id=%(execution_id)s %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    return ExecutionLogger(logging.getLogger("travel_ingestion"), {"execution_id": "-"})


class ExecutionLogger(logging.LoggerAdapter):
    """Logger adapter that safely adds an execution ID to every message."""

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("execution_id", self.extra.get("execution_id", "-"))
        return msg, kwargs


def with_execution_id(logger: logging.Logger, execution_id: str) -> ExecutionLogger:
    """Create a logger adapter scoped to one pipeline execution."""
    return ExecutionLogger(logger, {"execution_id": execution_id})

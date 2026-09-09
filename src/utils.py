"""Shared pipeline utilities, application error, and HTTP status mapping."""

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd


class PipelineError(Exception):
    """Expected pipeline error carrying the HTTP status the API should return."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


# Built-in exceptions raised inside pipeline modules, mapped to HTTP responses.
# PermissionError -> 403, FileNotFoundError -> 404, ValueError -> 422 (data issues).
EXPECTED_ERRORS = (PipelineError, PermissionError, FileNotFoundError, ValueError)


def http_status(exc: Exception) -> int:
    """Return the HTTP status code for an exception (500 when unexpected)."""
    if isinstance(exc, PipelineError):
        return exc.status_code
    if isinstance(exc, PermissionError):
        return 403
    if isinstance(exc, FileNotFoundError):
        return 404
    if isinstance(exc, ValueError):
        return 422
    return 500


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def json_safe(value: Any) -> Any:
    """Convert pandas and datetime values into JSON-serializable values."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value

"""Shared pipeline utilities and application exceptions."""

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd


class PipelineError(Exception):
    """Expected pipeline error with an HTTP response status."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class RequestValidationError(PipelineError):
    """Raised when the API payload is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 400)


class SourceFileError(PipelineError):
    """Raised when a source object cannot be read or parsed."""


class EmptyFileError(SourceFileError):
    """Raised when the source contains no records."""

    def __init__(self) -> None:
        super().__init__("The CSV file is empty", 422)


class InvalidSchemaError(SourceFileError):
    """Raised when required source columns are absent."""

    def __init__(self, missing_columns: list[str]) -> None:
        super().__init__(
            f"Invalid CSV schema; missing columns: {', '.join(missing_columns)}", 422
        )


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def json_safe(value: Any) -> Any:
    """Convert pandas and datetime values into JSON-serializable values."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to records without NaN/NaT JSON values."""
    return [
        {key: json_safe(value) for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]

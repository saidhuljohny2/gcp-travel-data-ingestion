"""Transform valid and rejected employee travel records."""

from datetime import datetime
import logging

import pandas as pd

def _trim_strings(frame: pd.DataFrame) -> None:
    for column in frame.columns:
        if frame[column].dtype == "object":
            frame[column] = frame[column].astype(str).str.strip()


def transform_valid_records(
    frame: pd.DataFrame,
    source_file: str,
    execution_id: str,
    processed_at: datetime,
    logger: logging.Logger,
) -> pd.DataFrame:
    """Standardize valid records and add calculated and lineage fields."""
    transformed = frame.drop(columns=["rejection_reason"], errors="ignore").copy()
    _trim_strings(transformed)
    transformed["employee_name"] = transformed["employee_name"].str.title()
    transformed["origin_city"] = transformed["origin_city"].str.title()
    transformed["destination_city"] = transformed["destination_city"].str.title()
    transformed["booking_status"] = transformed["booking_status"].str.upper()
    transformed["currency"] = transformed["currency"].str.upper()
    transformed["travel_duration_days"] = (
        transformed["return_date"] - transformed["travel_date"]
    ).dt.days.astype("Int64")
    # BigQuery DATE expects date values rather than pandas timestamps.
    transformed["travel_date"] = transformed["travel_date"].dt.date
    transformed["return_date"] = transformed["return_date"].dt.date
    transformed["processed_at"] = processed_at
    transformed["source_file"] = source_file
    transformed["execution_id"] = execution_id
    logger.info("Transformation completed for %d valid records", len(transformed))
    return transformed


def transform_rejected_records(
    frame: pd.DataFrame,
    source_file: str,
    execution_id: str,
    rejected_at: datetime,
) -> pd.DataFrame:
    """Normalize rejected values and append rejection lineage."""
    rejected = frame.copy()
    _trim_strings(rejected)
    rejected["source_file"] = source_file
    rejected["execution_id"] = execution_id
    rejected["rejected_at"] = rejected_at
    return rejected

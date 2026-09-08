"""Data quality rules for employee travel records."""

import logging

import pandas as pd

from src.utils import InvalidSchemaError

REQUIRED_COLUMNS = [
    "booking_id",
    "employee_id",
    "employee_name",
    "department",
    "origin_city",
    "destination_city",
    "travel_date",
    "return_date",
    "travel_type",
    "airline",
    "ticket_price",
    "currency",
    "booking_status",
]
VALID_STATUSES = {"CONFIRMED", "PENDING", "CANCELLED"}


def _blank(series: pd.Series) -> pd.Series:
    """Identify null, empty, or whitespace-only values."""
    return series.isna() | series.astype(str).str.strip().eq("")


def validate_records(
    frame: pd.DataFrame, logger: logging.Logger
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split records into valid and rejected frames with rejection reasons."""
    logger.info("Validation started for %d records", len(frame))
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise InvalidSchemaError(missing)

    working = frame[REQUIRED_COLUMNS].copy()
    travel_dates = pd.to_datetime(working["travel_date"].str.strip(), errors="coerce")
    return_dates = pd.to_datetime(working["return_date"].str.strip(), errors="coerce")
    prices = pd.to_numeric(working["ticket_price"].str.strip(), errors="coerce")
    statuses = working["booking_status"].str.strip().str.upper()

    reasons: list[list[str]] = [[] for _ in range(len(working))]

    def reject(mask: pd.Series, reason: str) -> None:
        for position in mask.fillna(False).to_numpy().nonzero()[0]:
            reasons[position].append(reason)

    reject(_blank(working["booking_id"]), "booking_id is missing")
    reject(
        working["booking_id"].str.strip().duplicated(keep="first")
        & ~_blank(working["booking_id"]),
        "duplicate booking_id in source file",
    )
    reject(_blank(working["employee_id"]), "employee_id is missing")
    reject(_blank(working["employee_name"]), "employee_name is missing")
    reject(prices.isna() | prices.le(0), "ticket_price must be greater than zero")
    reject(travel_dates.isna(), "travel_date is invalid")
    reject(return_dates.isna(), "return_date is invalid")
    reject(
        travel_dates.notna() & return_dates.notna() & return_dates.lt(travel_dates),
        "return_date is earlier than travel_date",
    )
    reject(~statuses.isin(VALID_STATUSES), "booking_status is invalid")

    working["rejection_reason"] = ["; ".join(items) for items in reasons]
    rejected_mask = working["rejection_reason"].ne("")
    valid = working.loc[~rejected_mask].copy()
    rejected = working.loc[rejected_mask].copy()

    valid["travel_date"] = travel_dates.loc[valid.index]
    valid["return_date"] = return_dates.loc[valid.index]
    # float64 is required for load_table_from_dataframe; BigQuery maps it to NUMERIC.
    valid["ticket_price"] = prices.loc[valid.index].astype("float64")
    logger.info(
        "Validation completed: valid=%d rejected=%d", len(valid), len(rejected)
    )
    return valid, rejected

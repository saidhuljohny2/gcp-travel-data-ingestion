"""Classroom demo: transform valid/rejected frames using production src.transformer.

Run from the repo root:
    python development/demo_transformer.py
"""

from pathlib import Path
from uuid import uuid4
import logging
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.cloud import storage
from src.gcs_reader import read_csv_from_gcs
from src.transformer import transform_rejected_records, transform_valid_records
from src.utils import utc_now
from src.validator import validate_records

BUCKET = "travel_landing_bkt"
FILE = "incoming/employee_travel_20260907.csv"

COMPARE_COLS = ["employee_name", "origin_city", "destination_city", "booking_status", "currency"]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("demo_transformer")
    client = storage.Client()

    execution_id = str(uuid4())
    processed_at = utc_now()

    frame = read_csv_from_gcs(BUCKET, FILE, client, logger)
    valid, rejected = validate_records(frame, logger)

    before = valid[COMPARE_COLS].head(8).copy()
    clean = transform_valid_records(valid, FILE, execution_id, processed_at, logger)
    rejected_out = transform_rejected_records(rejected, FILE, execution_id, processed_at)

    print(f"execution_id: {execution_id}")
    print(f"valid in: {len(valid)}  transformed: {len(clean)}  rejected: {len(rejected_out)}")
    print()
    print("Before transform (valid sample):")
    print(before.to_string(index=False))
    print()
    print("After transform (same rows: title case, UPPER status/currency, duration, lineage):")
    after_cols = COMPARE_COLS + ["travel_duration_days", "source_file", "execution_id"]
    print(clean[after_cols].head(8).to_string(index=False))
    print()
    print("Rejected after transform (original values + lineage; dates stay strings):")
    rej_cols = ["booking_id", "booking_status", "rejection_reason", "source_file", "execution_id"]
    print(rejected_out[rej_cols].head(5).to_string(index=False))

"""Classroom demo: validate a GCS CSV using production src.validator.

Run from the repo root:
    python development/demo_validator.py
"""

from pathlib import Path
import logging
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.cloud import storage

from src.gcs_reader import read_csv_from_gcs
from src.validator import validate_records

BUCKET = "travel-incoming-gcp-evening-batch-501811"
FILE = "incoming/employee_travel_20260907.csv"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("demo_validator")
    client = storage.Client()

    frame = read_csv_from_gcs(BUCKET, FILE, client, logger)
    valid, rejected = validate_records(frame, logger)

    print(f"records_read:      {len(frame)}")
    print(f"records_loaded:    {len(valid)}")
    print(f"records_rejected:  {len(rejected)}")
    print()
    print("Rejection reasons:")
    print(rejected["rejection_reason"].value_counts().to_string())
    print()
    print("Sample rejected rows:")
    cols = ["booking_id", "employee_id", "employee_name", "ticket_price", "travel_date", "return_date", "booking_status", "rejection_reason"]
    print(rejected[cols].head(10).to_string(index=False))

"""Classroom demo: call production src.gcs_reader.read_csv_from_gcs.

Run from the repo root:
    python development/demo_gcs_reader.py
"""

from pathlib import Path
import logging
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.cloud import storage
from src.gcs_reader import read_csv_from_gcs

BUCKET = "travel_landing_bkt"
FILE = "incoming/employee_travel_20260907.csv"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("demo_gcs_reader")
    client = storage.Client()

    df = read_csv_from_gcs(BUCKET, FILE, client, logger)
    print(df)
    print(f"Total records: {len(df)}")

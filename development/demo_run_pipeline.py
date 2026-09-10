"""Classroom demo: call production src.pipeline.run_pipeline (no Flask).

This is the glue after the per-module demos. Same function Cloud Run uses
for POST /load and POST /events.

Writes BigQuery (staging, MERGE, rejected, audit). Run from the repo root:

    python development/demo_run_pipeline.py
    python development/demo_run_pipeline.py --file incoming/employee_travel_20260908.csv
"""

from pathlib import Path
import argparse
import json
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GCP_PROJECT_ID", "morning-batch-gcp-501901")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "morning-batch-gcp-501901")

from src.config import Config
from src.logger import configure_logging
from src.pipeline import run_pipeline

DEFAULT_BUCKET = os.getenv("DEMO_BUCKET", "travel_landing_bkt")
DEFAULT_FILE = os.getenv("DEMO_FILE", "incoming/employee_travel_20260907.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full GCS → BigQuery chain (src.pipeline.run_pipeline)."
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--file", default=DEFAULT_FILE)
    args = parser.parse_args()

    configure_logging("INFO")
    logging.getLogger("travel_ingestion").info(
        "demo_run_pipeline calling src.pipeline.run_pipeline gs://%s/%s",
        args.bucket,
        args.file,
    )

    print("Chain (same as app.py):")
    print("  read_csv_from_gcs → validate_records → transform_*")
    print("  → load_staging → merge_final → load_rejected → write_audit")
    print()

    config = Config.from_env()
    body, status = run_pipeline(args.bucket, args.file, config=config)
    print(f"HTTP-equivalent status: {status}")
    print(json.dumps(body, indent=2))
    raise SystemExit(0 if status == 200 else 1)

"""Classroom demo: load transformed rows into BigQuery (same steps as POST /load).

Writes to travel_staging, employee_travel (MERGE), travel_rejected, pipeline_audit.

Run from the repo root (ADC user needs BigQuery Data Editor + Job User):
    python development/demo_bigquery_loader.py
"""

from pathlib import Path
from uuid import uuid4
import logging
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GCP_PROJECT_ID", "morning-batch-gcp-501901")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "morning-batch-gcp-501901")

from google.cloud import bigquery, storage

from src.audit import AuditRecord, write_audit
from src.bigquery_loader import BigQueryLoader
from src.config import Config
from src.gcs_reader import read_csv_from_gcs
from src.transformer import transform_rejected_records, transform_valid_records
from src.utils import utc_now
from src.validator import validate_records

BUCKET = "travel_landing_bkt"
FILE = "incoming/employee_travel_20260907.csv"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("demo_bigquery_loader")

    execution_id = str(uuid4())
    start_time = utc_now()
    started = time.monotonic()

    config = Config.from_env()
    gcs = storage.Client(project=config.project_id)
    bq = bigquery.Client(project=config.project_id, location=config.bq_location)
    loader = BigQueryLoader(bq, config, logger)

    frame = read_csv_from_gcs(BUCKET, FILE, gcs, logger)
    valid, rejected = validate_records(frame, logger)
    processed_at = utc_now()
    clean = transform_valid_records(valid, FILE, execution_id, processed_at, logger)
    rejected = transform_rejected_records(rejected, FILE, execution_id, processed_at)

    logger.info("BigQuery load started")
    loader.load_staging(clean)
    loader.merge_final(execution_id)
    loader.load_rejected(rejected)
    logger.info("BigQuery load completed")

    end_time = utc_now()
    duration = time.monotonic() - started
    write_audit(
        bq,
        config,
        AuditRecord(
            execution_id=execution_id,
            file_name=FILE,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=round(duration, 3),
            records_read=len(frame),
            records_loaded=len(clean),
            records_rejected=len(rejected),
            status="SUCCESS",
        ),
        logger,
    )

    print()
    print(
        {
            "status": "SUCCESS",
            "execution_id": execution_id,
            "records_read": len(frame),
            "records_loaded": len(clean),
            "records_rejected": len(rejected),
            "processing_time": f"{duration:.2f} seconds",
        }
    )
    print()
    print("Latest audit rows:")
    for row in loader.latest_audits(3):
        print(
            row.get("execution_id"),
            row.get("file_name"),
            row.get("status"),
            row.get("records_loaded"),
            row.get("records_rejected"),
        )

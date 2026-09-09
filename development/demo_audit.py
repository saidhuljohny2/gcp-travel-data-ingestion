"""Classroom demo: read pipeline_audit (same query as GET /audit).

Read-only. Does not load GCS or write BigQuery.

Run from the repo root:
    python development/demo_audit.py
"""

from pathlib import Path
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GCP_PROJECT_ID", "gcp-evening-batch-501811")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "gcp-evening-batch-501811")

from google.cloud import bigquery

from src.bigquery_loader import BigQueryLoader
from src.config import Config
from src.utils import json_safe

LIMIT = 5


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("demo_audit")

    config = Config.from_env()
    bq = bigquery.Client(project=config.project_id, location=config.bq_location)
    loader = BigQueryLoader(bq, config, logger)

    rows = loader.latest_audits(LIMIT)
    print(f"Latest {len(rows)} pipeline_audit rows (GET /audit):")
    print()
    for row in rows:
        safe = {key: json_safe(value) for key, value in row.items()}
        print(
            f"{safe.get('start_time')}  {safe.get('status'):8}  "
            f"read={safe.get('records_read')}  loaded={safe.get('records_loaded')}  "
            f"rejected={safe.get('records_rejected')}  "
            f"{safe.get('file_name')}"
        )
        print(f"  execution_id={safe.get('execution_id')}")
        if safe.get("error_message"):
            print(f"  error={safe.get('error_message')}")
        print()

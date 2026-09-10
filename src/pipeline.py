"""GCS-to-BigQuery orchestration shared by Cloud Run and classroom demos."""

from dataclasses import replace
import logging
import time
from typing import Any
from uuid import uuid4

from google.cloud import bigquery, storage

from src.audit import AuditRecord, write_audit
from src.bigquery_loader import BigQueryLoader
from src.config import Config
from src.gcs_reader import read_csv_from_gcs
from src.logger import with_execution_id
from src.transformer import transform_rejected_records, transform_valid_records
from src.utils import EXPECTED_ERRORS, PipelineError, http_status, utc_now
from src.validator import validate_records


def resolve_clients(
    config: Config,
    storage_client: storage.Client | None = None,
    bigquery_client: bigquery.Client | None = None,
) -> tuple[storage.Client, bigquery.Client, Config]:
    """Build GCS/BigQuery clients and fill project_id from ADC when unset."""
    bq = bigquery_client or bigquery.Client(
        project=config.project_id or None, location=config.bq_location
    )
    gcs = storage_client or storage.Client(project=config.project_id or bq.project)
    resolved = config
    if not config.project_id:
        resolved = replace(config, project_id=bq.project)
    return gcs, bq, resolved


def run_pipeline(
    bucket: str,
    file_name: str,
    *,
    config: Config,
    storage_client: storage.Client | None = None,
    bigquery_client: bigquery.Client | None = None,
    invalid_request: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Run the same chain as POST /load and POST /events. Returns (body, HTTP status)."""
    execution_id = str(uuid4())
    execution_logger = with_execution_id(
        logging.getLogger("travel_ingestion"), execution_id
    )
    start_time = utc_now()
    started = time.monotonic()
    records_read = records_loaded = records_rejected = 0
    bq: bigquery.Client | None = None
    resolved = config

    try:
        if invalid_request:
            raise PipelineError(invalid_request, 400)
        if not bucket:
            raise PipelineError("'bucket' is required", 400)
        if not file_name:
            raise PipelineError("'file' is required", 400)
        if not file_name.lower().endswith(".csv"):
            raise PipelineError("'file' must reference a CSV object", 400)

        gcs, bq, resolved = resolve_clients(config, storage_client, bigquery_client)
        source = read_csv_from_gcs(bucket, file_name, gcs, execution_logger)
        records_read = len(source)
        valid, rejected = validate_records(source, execution_logger)
        processed_at = utc_now()
        clean = transform_valid_records(
            valid, file_name, execution_id, processed_at, execution_logger
        )
        rejected = transform_rejected_records(
            rejected, file_name, execution_id, processed_at
        )
        records_loaded = len(clean)
        records_rejected = len(rejected)

        loader = BigQueryLoader(bq, resolved, execution_logger)
        loader.load_staging(clean)
        loader.merge_final(execution_id)
        loader.load_rejected(rejected)

        duration = time.monotonic() - started
        write_audit(
            bq,
            resolved,
            AuditRecord(
                execution_id=execution_id,
                file_name=file_name,
                start_time=start_time,
                end_time=utc_now(),
                duration_seconds=round(duration, 3),
                records_read=records_read,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
                status="SUCCESS",
            ),
            execution_logger,
        )
        execution_logger.info("Pipeline success")
        return {
            "status": "SUCCESS",
            "execution_id": execution_id,
            "records_read": records_read,
            "records_loaded": records_loaded,
            "records_rejected": records_rejected,
            "processing_time": f"{duration:.2f} seconds",
        }, 200

    except Exception as exc:
        status_code = http_status(exc)
        message = str(exc) if isinstance(exc, EXPECTED_ERRORS) else "Unexpected server error"
        execution_logger.exception("Pipeline failure: %s", exc)
        if bq is None:
            try:
                _, bq, resolved = resolve_clients(
                    config, storage_client, bigquery_client
                )
            except Exception:
                execution_logger.exception("Unable to initialize audit client")
        if bq is not None:
            try:
                write_audit(
                    bq,
                    resolved,
                    AuditRecord(
                        execution_id=execution_id,
                        file_name=file_name,
                        start_time=start_time,
                        end_time=utc_now(),
                        duration_seconds=round(time.monotonic() - started, 3),
                        records_read=records_read,
                        records_loaded=records_loaded,
                        records_rejected=records_rejected,
                        status="FAILED",
                        error_message=str(exc)[:1024],
                    ),
                    execution_logger,
                )
            except Exception:
                execution_logger.exception("Unable to persist failure audit")
        return {
            "status": "FAILED",
            "execution_id": execution_id,
            "message": message,
        }, status_code

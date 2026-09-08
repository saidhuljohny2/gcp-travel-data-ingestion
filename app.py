"""Flask API for the GCP Travel Data Ingestion Platform."""

from dataclasses import replace
import logging
import os
import time
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, request
from google.cloud import bigquery, storage

from src.audit import AuditRecord, write_audit
from src.bigquery_loader import BigQueryLoader
from src.config import Config
from src.gcs_reader import read_csv_from_gcs
from src.logger import configure_logging, with_execution_id
from src.transformer import transform_rejected_records, transform_valid_records
from src.utils import PipelineError, RequestValidationError, json_safe, utc_now
from src.validator import validate_records


def create_app(
    config: Config | None = None,
    storage_client: storage.Client | None = None,
    bigquery_client: bigquery.Client | None = None,
) -> Flask:
    """Application factory supporting dependency injection for tests."""
    app = Flask(__name__)
    settings = config or Config.from_env()
    logger = configure_logging(settings.log_level)
    logger.info("API started")

    def clients() -> tuple[storage.Client, bigquery.Client, Config]:
        bq = bigquery_client or bigquery.Client(
            project=settings.project_id or None, location=settings.bq_location
        )
        gcs = storage_client or storage.Client(project=settings.project_id or bq.project)
        resolved = settings
        if not settings.project_id:
            resolved = replace(settings, project_id=bq.project)
        return gcs, bq, resolved

    @app.get("/")
    def health() -> tuple[Any, int]:
        """Liveness endpoint that does not require GCP connectivity."""
        return jsonify(
            service="gcp-travel-data-ingestion",
            status="UP",
            version="1.0.0",
        ), 200

    @app.get("/audit")
    def audits() -> tuple[Any, int]:
        """Return the latest pipeline audit records."""
        try:
            _, bq, resolved = clients()
            requested_limit = request.args.get("limit", resolved.audit_limit, type=int)
            limit = max(1, min(requested_limit or resolved.audit_limit, 100))
            rows = BigQueryLoader(bq, resolved, logger).latest_audits(limit)
            payload = [
                {key: json_safe(value) for key, value in row.items()} for row in rows
            ]
            return jsonify(status="SUCCESS", executions=payload), 200
        except PipelineError as exc:
            logger.error("Audit lookup failed: %s", exc)
            return jsonify(status="FAILED", message=str(exc)), exc.status_code
        except Exception:
            logger.exception("Unexpected audit lookup failure")
            return jsonify(status="FAILED", message="Unexpected server error"), 500

    @app.post("/load")
    def load() -> tuple[Any, int]:
        """Run the GCS-to-BigQuery pipeline for one CSV object."""
        execution_id = str(uuid4())
        execution_logger = with_execution_id(
            logging.getLogger("travel_ingestion"), execution_id
        )
        start_time = utc_now()
        started = time.monotonic()
        file_name = ""
        records_read = records_loaded = records_rejected = 0
        bq: bigquery.Client | None = None
        resolved = settings

        try:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                raise RequestValidationError("Request body must be a JSON object")
            bucket = str(payload.get("bucket", "")).strip()
            file_name = str(payload.get("file", "")).strip()
            if not bucket:
                raise RequestValidationError("'bucket' is required")
            if not file_name:
                raise RequestValidationError("'file' is required")
            if not file_name.lower().endswith(".csv"):
                raise RequestValidationError("'file' must reference a CSV object")

            gcs, bq, resolved = clients()
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

            end_time = utc_now()
            duration = time.monotonic() - started
            write_audit(
                bq,
                resolved,
                AuditRecord(
                    execution_id=execution_id,
                    file_name=file_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=round(duration, 3),
                    records_read=records_read,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                    status="SUCCESS",
                ),
                execution_logger,
            )
            execution_logger.info("Pipeline success")
            return jsonify(
                status="SUCCESS",
                execution_id=execution_id,
                records_read=records_read,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
                processing_time=f"{duration:.2f} seconds",
            ), 200

        except Exception as exc:
            status_code = exc.status_code if isinstance(exc, PipelineError) else 500
            message = str(exc) if isinstance(exc, PipelineError) else "Unexpected server error"
            execution_logger.exception("Pipeline failure: %s", exc)
            # API-validation failures happen before data clients are needed. Make a
            # best-effort client initialization so those executions are audited too.
            if bq is None:
                try:
                    _, bq, resolved = clients()
                except Exception:
                    execution_logger.exception("Unable to initialize audit client")
            if bq is not None:
                end_time = utc_now()
                try:
                    write_audit(
                        bq,
                        resolved,
                        AuditRecord(
                            execution_id=execution_id,
                            file_name=file_name,
                            start_time=start_time,
                            end_time=end_time,
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
            return jsonify(
                status="FAILED",
                execution_id=execution_id,
                message=message,
            ), status_code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

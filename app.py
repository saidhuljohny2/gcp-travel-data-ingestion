"""Flask API for the GCP Travel Data Ingestion Platform."""

import logging
import os
from typing import Any

from flask import Flask, jsonify, request
from google.cloud import bigquery, storage

from src.bigquery_loader import BigQueryLoader
from src.config import Config
from src.gcs_event import storage_object_from_request
from src.logger import configure_logging
from src.pipeline import resolve_clients, run_pipeline
from src.utils import EXPECTED_ERRORS, http_status, json_safe


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

    def pipeline(bucket: str, file_name: str, **kwargs: Any) -> tuple[Any, int]:
        body, status = run_pipeline(
            bucket,
            file_name,
            config=settings,
            storage_client=storage_client,
            bigquery_client=bigquery_client,
            **kwargs,
        )
        return jsonify(body), status

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
            _, bq, resolved = resolve_clients(settings, storage_client, bigquery_client)
            requested_limit = request.args.get("limit", resolved.audit_limit, type=int)
            limit = max(1, min(requested_limit or resolved.audit_limit, 100))
            rows = BigQueryLoader(bq, resolved, logger).latest_audits(limit)
            payload = [
                {key: json_safe(value) for key, value in row.items()} for row in rows
            ]
            return jsonify(status="SUCCESS", executions=payload), 200
        except EXPECTED_ERRORS as exc:
            logger.error("Audit lookup failed: %s", exc)
            return jsonify(status="FAILED", message=str(exc)), http_status(exc)
        except Exception:
            logger.exception("Unexpected audit lookup failure")
            return jsonify(status="FAILED", message="Unexpected server error"), 500

    @app.post("/load")
    def load() -> tuple[Any, int]:
        """Manual trigger: JSON body {bucket, file} runs the pipeline."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return pipeline("", "", invalid_request="Request body must be a JSON object")
        bucket = str(payload.get("bucket", "")).strip()
        file_name = str(payload.get("file", "")).strip()
        return pipeline(bucket, file_name)

    @app.post("/events")
    def events() -> tuple[Any, int]:
        """Eventarc destination: Cloud Storage object-finalized CloudEvents."""
        parsed = storage_object_from_request(request)
        if parsed is None:
            logger.info("Ignoring Eventarc event (not incoming/*.csv)")
            return ("", 204)
        bucket, file_name = parsed
        logger.info("Eventarc object finalized: gs://%s/%s", bucket, file_name)
        return pipeline(bucket, file_name)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

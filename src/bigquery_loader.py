"""BigQuery load jobs, idempotent merge, and audit query operations."""

import logging
from typing import Any
from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import bigquery
import pandas as pd
from src.config import Config
from src.utils import PipelineError

FINAL_COLUMNS = [
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
    "travel_duration_days",
    "processed_at",
    "source_file",
    "execution_id",
]

STAGING_SCHEMA = [
    bigquery.SchemaField("booking_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("employee_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("employee_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("department", "STRING"),
    bigquery.SchemaField("origin_city", "STRING"),
    bigquery.SchemaField("destination_city", "STRING"),
    bigquery.SchemaField("travel_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("return_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("travel_type", "STRING"),
    bigquery.SchemaField("airline", "STRING"),
    bigquery.SchemaField("ticket_price", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("currency", "STRING"),
    bigquery.SchemaField("booking_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("travel_duration_days", "INT64"),
    bigquery.SchemaField("processed_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("source_file", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("execution_id", "STRING", mode="REQUIRED"),
]

REJECTED_SCHEMA = [
    *[bigquery.SchemaField(name, "STRING") for name in FINAL_COLUMNS[:13]],
    bigquery.SchemaField("rejection_reason", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_file", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("execution_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rejected_at", "TIMESTAMP", mode="REQUIRED"),
]


class BigQueryLoader:
    """Encapsulate all BigQuery interactions used by the pipeline."""

    def __init__(self, client: bigquery.Client, config: Config, logger: logging.Logger) -> None:
        self.client = client
        self.config = config
        self.logger = logger

    def _run(self, operation: Any) -> Any:
        try:
            return operation()
        except Forbidden as exc:
            raise PipelineError("BigQuery permission denied", 403) from exc
        except NotFound as exc:
            raise PipelineError("BigQuery dataset or table not found; run the SQL setup scripts", 500) from exc

    def load_staging(self, frame: pd.DataFrame) -> None:
        """Append validated records to staging for the current execution."""

        if frame.empty:
            return
        self.logger.info("BigQuery staging load started")
        config = bigquery.LoadJobConfig(
            schema=STAGING_SCHEMA,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        self._run(lambda: self.client.load_table_from_dataframe(frame, self.config.table_id(self.config.staging_table), job_config=config).result())
        self.logger.info("BigQuery staging load completed")

    def merge_final(self, execution_id: str) -> None:
        """Upsert one execution from staging, making replay idempotent by booking_id."""

        target = self.config.table_id(self.config.final_table)
        staging = self.config.table_id(self.config.staging_table)
        update_columns = [name for name in FINAL_COLUMNS if name != "booking_id"]
        assignments = ",\n      ".join(f"T.{name} = S.{name}" for name in update_columns)
        columns = ", ".join(FINAL_COLUMNS)
        source_columns = ", ".join(f"S.{name}" for name in FINAL_COLUMNS)
        query = f"""
        MERGE `{target}` T
        USING (
          SELECT * EXCEPT(row_number)
          FROM (
            SELECT *, ROW_NUMBER() OVER (
              PARTITION BY booking_id ORDER BY processed_at DESC
            ) AS row_number
            FROM `{staging}`
            WHERE execution_id = @execution_id
          )
          WHERE row_number = 1
        ) S
        ON T.booking_id = S.booking_id
        WHEN MATCHED THEN UPDATE SET
          {assignments}
        WHEN NOT MATCHED THEN
          INSERT ({columns}) VALUES ({source_columns})
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id)
            ]
        )
        self._run(lambda: self.client.query(query, job_config=job_config).result())
        self.logger.info("BigQuery final merge completed")

    def load_rejected(self, frame: pd.DataFrame) -> None:
        """Append invalid records and their reasons to the rejected table."""

        if frame.empty:
            return
        config = bigquery.LoadJobConfig(
            schema=REJECTED_SCHEMA,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        self._run(lambda: self.client.load_table_from_dataframe(frame,self.config.table_id(self.config.rejected_table),job_config=config,).result())
        self.logger.warning("Loaded %d rejected records", len(frame))

    def latest_audits(self, limit: int) -> list[dict[str, Any]]:
        """Return recent pipeline executions."""
        query = f"""
        SELECT *
        FROM `{self.config.table_id(self.config.audit_table)}`
        ORDER BY start_time DESC
        LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        )
        rows = self._run(lambda: self.client.query(query, job_config=job_config).result())
        return [dict(row.items()) for row in rows]

"""Pipeline execution audit model and BigQuery persistence."""

from dataclasses import asdict, dataclass
from datetime import datetime
import logging
from typing import Any

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import bigquery

from src.config import Config
from src.utils import PipelineError


@dataclass
class AuditRecord:
    """One immutable summary of a pipeline execution."""

    execution_id: str
    file_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    records_read: int
    records_loaded: int
    records_rejected: int
    status: str
    error_message: str | None = None

    def as_json(self) -> dict[str, Any]:
        """Convert timestamps to RFC 3339 values for BigQuery streaming insert."""
        record = asdict(self)
        record["start_time"] = self.start_time.isoformat()
        record["end_time"] = self.end_time.isoformat()
        return record


def write_audit(
    client: bigquery.Client,
    config: Config,
    record: AuditRecord,
    logger: logging.Logger,
) -> None:
    """Insert one audit record; raise a clear error when persistence fails."""
    try:
        errors = client.insert_rows_json(
            config.table_id(config.audit_table), [record.as_json()]
        )
    except Forbidden as exc:
        raise PipelineError("BigQuery permission denied while writing audit", 403) from exc
    except NotFound as exc:
        raise PipelineError("BigQuery audit table not found", 500) from exc
    if errors:
        raise PipelineError(f"BigQuery audit insert failed: {errors}", 500)
    logger.info("Audit written with status=%s", record.status)

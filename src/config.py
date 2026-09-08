"""Application configuration loaded exclusively from environment variables."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    """Runtime settings for GCP resources and the Flask service."""

    project_id: str
    bq_dataset: str = "travel_analytics"
    bq_location: str = "US"
    staging_table: str = "travel_staging"
    final_table: str = "employee_travel"
    rejected_table: str = "travel_rejected"
    audit_table: str = "pipeline_audit"
    port: int = 8080
    log_level: str = "INFO"
    audit_limit: int = 20

    @classmethod
    def from_env(cls) -> "Config":
        """Build configuration, using the ADC project when possible."""
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        return cls(
            project_id=project_id,
            bq_dataset=os.getenv("BQ_DATASET", "travel_analytics"),
            bq_location=os.getenv("BQ_LOCATION", "US"),
            port=int(os.getenv("PORT", "8080")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            audit_limit=int(os.getenv("AUDIT_LIMIT", "20")),
        )

    def table_id(self, table_name: str) -> str:
        """Return a fully-qualified BigQuery table identifier."""
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be configured")
        return f"{self.project_id}.{self.bq_dataset}.{table_name}"

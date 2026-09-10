"""Read CSV source objects from Google Cloud Storage."""

from io import BytesIO
import logging

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import storage
import pandas as pd


def read_csv_from_gcs(bucket_name: str, object_name: str, client: storage.Client, logger: logging.Logger) -> pd.DataFrame:
    """Download and parse a GCS object as a string-preserving DataFrame."""
    logger.info("File received: gs://%s/%s", bucket_name, object_name)
    try:
        payload = client.bucket(bucket_name).blob(object_name).download_as_bytes()
    except NotFound as exc:
        raise FileNotFoundError(f"GCS object not found: gs://{bucket_name}/{object_name}") from exc
    except Forbidden as exc:
        raise PermissionError("GCS permission denied while reading source file") from exc

    if not payload.strip():
        raise ValueError("The CSV file is empty")

    try:
        frame = pd.read_csv(BytesIO(payload), dtype=str, keep_default_na=False, na_filter=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValueError(f"Unable to parse CSV: {exc}") from exc

    if frame.empty:
        raise ValueError("The CSV file is empty")
    return frame
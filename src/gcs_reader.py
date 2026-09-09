"""Read CSV source objects from Google Cloud Storage."""

from io import BytesIO
import logging

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import storage
import pandas as pd

from src.utils import EmptyFileError, PipelineError, SourceFileError


def read_csv_from_gcs(
    bucket_name: str,
    object_name: str,
    client: storage.Client,
    logger: logging.Logger,
) -> pd.DataFrame:
    """Download and parse a GCS object as a string-preserving DataFrame."""
    logger.info("File received: gs://%s/%s", bucket_name, object_name)
    try:
        payload = client.bucket(bucket_name).blob(object_name).download_as_bytes()
    except NotFound as exc:
        raise SourceFileError(
            f"GCS object not found: gs://{bucket_name}/{object_name}", 404
        ) from exc
    except Forbidden as exc:
        raise PipelineError("GCS permission denied while reading source file", 403) from exc

    if not payload.strip():
        raise EmptyFileError()

    try:
        frame = pd.read_csv(
            BytesIO(payload),
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise SourceFileError(f"Unable to parse CSV: {exc}", 422) from exc

    if frame.empty:
        raise EmptyFileError()
    return frame

# for manual testing
# logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
# logger = logging.getLogger("gcs_reader_demo")
# client = storage.Client()

# frame = read_csv_from_gcs(
#     "travel-incoming-gcp-evening-batch-501811",
#     "incoming/employee_travel_20260907.csv",
#     client,
#     logger,
# )
# print(frame)
# print(len(frame))
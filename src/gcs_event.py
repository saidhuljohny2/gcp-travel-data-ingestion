"""Parse Cloud Storage object events delivered by Eventarc (CloudEvents)."""

from collections.abc import Mapping
from typing import Any

INCOMING_PREFIX = "incoming/"
FINALIZED_TYPE = "google.cloud.storage.object.v1.finalized"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def storage_object_from_payload(
    payload: Any,
    headers: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    """Return (bucket, object_name) for an incoming/*.csv object, else None.

    Eventarc uses CloudEvents binary mode: GCS object JSON in the body,
    type in the ``ce-type`` header. Structured mode puts the same fields
    under ``data``. Non-CSV or non-incoming objects are ignored (None)
    so Eventarc does not retry folder markers or unrelated uploads.
    """
    if not isinstance(payload, dict):
        return None

    header_map = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    event_type = (header_map.get("ce-type") or str(payload.get("type") or "")).strip()
    if event_type and event_type != FINALIZED_TYPE:
        return None

    data = _as_dict(payload.get("data")) if "data" in payload else payload
    bucket = str(data.get("bucket") or "").strip()
    name = str(data.get("name") or "").strip()

    if not name:
        subject = header_map.get("ce-subject", "").strip()
        if subject.startswith("objects/"):
            name = subject[len("objects/") :]

    if not bucket or not name:
        return None
    if name.endswith("/") or not name.startswith(INCOMING_PREFIX):
        return None
    if not name.lower().endswith(".csv"):
        return None
    return bucket, name


def storage_object_from_request(request: Any) -> tuple[str, str] | None:
    """Adapter for a Flask request (``get_json`` + ``headers``)."""
    return storage_object_from_payload(request.get_json(silent=True), request.headers)

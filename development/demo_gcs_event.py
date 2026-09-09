"""Classroom demo: Eventarc sends a CloudEvent; we keep only incoming/*.csv.

Does not call GCS, BigQuery, or Flask. Run from the repo root:

    python development/demo_gcs_event.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gcs_event import storage_object_from_payload  # noqa: E402

CASES = [
    (
        "dated incoming CSV (Eventarc binary mode)",
        {"ce-type": "google.cloud.storage.object.v1.finalized"},
        {"bucket": "travel-incoming-demo", "name": "incoming/employee_travel_20260910.csv"},
    ),
    (
        "structured CloudEvent envelope",
        {},
        {
            "type": "google.cloud.storage.object.v1.finalized",
            "data": {
                "bucket": "travel-incoming-demo",
                "name": "incoming/employee_travel_20260910.csv",
            },
        },
    ),
    (
        "folder marker — ignored",
        {"ce-type": "google.cloud.storage.object.v1.finalized"},
        {"bucket": "travel-incoming-demo", "name": "incoming/"},
    ),
    (
        "CSV outside incoming/ — ignored",
        {"ce-type": "google.cloud.storage.object.v1.finalized"},
        {"bucket": "travel-incoming-demo", "name": "employee_travel.csv"},
    ),
]


if __name__ == "__main__":
    for title, headers, body in CASES:
        print(f"{title}: {storage_object_from_payload(body, headers)}")

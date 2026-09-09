"""Classroom demo: the Cloud Run API is the same pipeline behind HTTP.

Default is read-only (health + audit). Pass --load to POST /load (writes BigQuery).

Run from the repo root:
    python development/demo_api.py
    python development/demo_api.py --load
    python development/demo_api.py --missing-file
"""

from pathlib import Path
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = os.getenv(
    "CLOUD_RUN_URL",
    "https://travel-ingestion-api-l4mjv2qmxq-uc.a.run.app",
).rstrip("/")
BUCKET = "travel-incoming-gcp-evening-batch-501811"
FILE = "incoming/employee_travel_20260907.csv"


def get_json(path: str) -> tuple[int, dict]:
    request = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode()) if exc.fp else {}
        return exc.code, body


def post_json(path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode()) if exc.fp else {}
        return exc.code, body


def show(title: str, status: int, body: dict) -> None:
    print(f"=== {title}  HTTP {status} ===")
    print(json.dumps(body, indent=2, default=str))
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Call the live Cloud Run travel API.")
    parser.add_argument(
        "--load",
        action="store_true",
        help="POST /load for the demo dated CSV (writes BigQuery).",
    )
    parser.add_argument(
        "--missing-file",
        action="store_true",
        help="POST /load with a missing object to show HTTP 404.",
    )
    args = parser.parse_args()

    print(f"Cloud Run: {BASE_URL}\n")

    show("GET /  (health, no GCP)", *get_json("/"))
    show("GET /audit?limit=3", *get_json("/audit?limit=3"))

    if args.load:
        show(
            "POST /load",
            *post_json("/load", {"bucket": BUCKET, "file": FILE}),
        )
        show("GET /audit?limit=1  (after load)", *get_json("/audit?limit=1"))

    if args.missing_file:
        show(
            "POST /load  missing object",
            *post_json(
                "/load",
                {"bucket": BUCKET, "file": "incoming/does-not-exist.csv"},
            ),
        )

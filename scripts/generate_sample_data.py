#!/usr/bin/env python3
"""Generate timestamped daily employee travel CSV files with intentional defects.

Naming convention (what the platform expects for daily drops):

    employee_travel_YYYYMMDD.csv

Each generated file contains realistic-but-messy rows plus a fixed set of
intentional data-quality problems so the validation and rejection tables are
demonstrable in class. The generator is deterministic (seeded per date), so a
given date always produces the same file.

Usage:
    python scripts/generate_sample_data.py                # default 3 days
    python scripts/generate_sample_data.py --days 5 --rows 500
    python scripts/generate_sample_data.py --dates 20260907 20260908 20260909
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
import random

FIELDS = [
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
]

NAMES = [
    "Aarav Sharma", "Emma Johnson", "Liam Chen", "Sofia Martinez",
    "Noah Williams", "Priya Patel", "Lucas Silva", "Mia Anderson",
    "Ethan Brown", "Olivia Davis", "Arjun Nair", "Isabella Rossi",
]
DEPARTMENTS = ["Engineering", "Finance", "Sales", "Human Resources", "Operations", "Marketing"]
# Intentionally inconsistent casing / padding; transform must clean these.
CITIES = [
    "new york", "LONDON", " singapore ", "San Francisco", "dubai",
    "PARIS", "tokyo", "Bengaluru", "Sydney", "Toronto",
]
AIRLINES = [
    "United Airlines", "Emirates", "Lufthansa", "Singapore Airlines",
    "Delta", "British Airways", "Air India", "Qantas",
]
TRAVEL_TYPES = ["Domestic", "International"]
STATUSES = ["CONFIRMED", "PENDING", "CANCELLED"]


def _build_clean_row(rng: random.Random, booking_seq: int, base_day: date) -> dict[str, str]:
    """Create one well-formed (but possibly messy-cased) booking row."""
    start = base_day + timedelta(days=rng.randint(0, 21))
    end = start + timedelta(days=rng.randint(1, 14))
    origin = rng.choice(CITIES)
    destination = rng.choice([c for c in CITIES if c.strip().lower() != origin.strip().lower()])
    name = rng.choice(NAMES)
    status = rng.choice(STATUSES)

    # Occasionally add padding/casing noise (valid; cleaned in transform).
    if booking_seq % 9 == 0:
        name = f"  {name.upper()}  "
    if booking_seq % 11 == 0:
        status = status.lower()
    currency = rng.choice(["USD", "EUR", "GBP", "INR"])
    if booking_seq % 13 == 0:
        currency = currency.lower()

    return {
        "booking_id": f"BKG{booking_seq:06d}",
        "employee_id": f"EMP{rng.randint(1, 350):05d}",
        "employee_name": name,
        "department": rng.choice(DEPARTMENTS),
        "origin_city": origin,
        "destination_city": destination,
        "travel_date": start.isoformat(),
        "return_date": end.isoformat(),
        "travel_type": rng.choice(TRAVEL_TYPES),
        "airline": rng.choice(AIRLINES),
        "ticket_price": f"{rng.uniform(120, 4200):.2f}",
        "currency": currency,
        "booking_status": status,
    }


def _inject_defects(rows: list[dict[str, str]], rng: random.Random) -> int:
    """Corrupt a fixed slice of rows to exercise every rejection rule.

    Returns the approximate number of rows expected to be rejected.
    """
    n = len(rows)
    # Reserve the last ~11% of rows for defects (leave earlier rows clean).
    start = int(n * 0.90)

    def block(offset: int, size: int = 2) -> range:
        lo = min(start + offset, n)
        hi = min(lo + size, n)
        return range(lo, hi)

    rejected = 0
    for i in block(0):   # return_date before travel_date
        travel = date.fromisoformat(rows[i]["travel_date"])
        rows[i]["return_date"] = (travel - timedelta(days=2)).isoformat()
        rejected += 1
    for i in block(2):   # invalid travel_date
        rows[i]["travel_date"] = "2026-99-42"
        rejected += 1
    for i in block(4):   # invalid booking_status
        rows[i]["booking_status"] = "APPROVED"
        rejected += 1
    for i in block(6):   # non-positive ticket_price
        rows[i]["ticket_price"] = "-50.00"
        rejected += 1
    for i in block(8):   # blank employee_name
        rows[i]["employee_name"] = "   "
        rejected += 1
    for i in block(10):  # missing employee_id
        rows[i]["employee_id"] = ""
        rejected += 1
    for i in block(12):  # duplicate booking_id (reuse an earlier id)
        rows[i]["booking_id"] = rows[i - start]["booking_id"]
        rejected += 1
    return rejected


def generate_file(day: date, rows_count: int, start_seq: int, out_dir: Path) -> Path:
    """Write one timestamped daily CSV and return its path."""
    rng = random.Random(int(day.strftime("%Y%m%d")))
    rows = [_build_clean_row(rng, start_seq + i, day) for i in range(rows_count)]
    expected_rejected = _inject_defects(rows, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"employee_travel_{day.strftime('%Y%m%d')}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"{out_path.name}: rows={rows_count} "
        f"expected_rejected~={expected_rejected} valid~={rows_count - expected_rejected}"
    )
    return out_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=3, help="Number of consecutive daily files.")
    parser.add_argument("--rows", type=int, default=300, help="Rows per daily file.")
    parser.add_argument(
        "--start-date",
        default="20260907",
        help="First file date as YYYYMMDD (used when --dates is omitted).",
    )
    parser.add_argument(
        "--dates",
        nargs="*",
        help="Explicit list of YYYYMMDD dates. Overrides --days/--start-date.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[1] / "data" / "incoming"),
        help="Output directory for generated files.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    out_dir = Path(args.out_dir)

    if args.dates:
        days = [datetime.strptime(d, "%Y%m%d").date() for d in args.dates]
    else:
        first = datetime.strptime(args.start_date, "%Y%m%d").date()
        days = [first + timedelta(days=i) for i in range(args.days)]

    # Distinct booking-id ranges per day so daily drops accumulate as new
    # bookings; MERGE still keeps the final table unique on booking_id.
    for index, day in enumerate(days):
        start_seq = 100001 + index * 1000
        generate_file(day, args.rows, start_seq, out_dir)


if __name__ == "__main__":
    main()

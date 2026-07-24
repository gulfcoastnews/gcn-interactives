#!/usr/bin/env python3
"""Fail publication if the generated mortality dataset is internally unsafe."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "mortality.json"
VALID_STATUSES = {"preliminary", "final"}
REQUIRED = {"fieldId", "date", "county", "cause", "causeCode", "status", "sourceAsOf"}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    value = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    meta = value.get("_meta", {})
    records = value.get("records", [])
    if meta.get("sample") is not False:
        fail("_meta.sample must be false")
    if not records:
        fail("records must not be empty")

    seen: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    for index, record in enumerate(records):
        missing = sorted(REQUIRED - record.keys())
        if missing:
            fail(f"record {index} is missing {missing}")
        try:
            parsed_date = date.fromisoformat(record["date"])
            date.fromisoformat(record["sourceAsOf"])
        except (TypeError, ValueError) as error:
            fail(f"record {index} has an invalid date: {error}")
        if parsed_date > datetime.now().date():
            fail(f"record {index} has a future report date")
        if record["status"] not in VALID_STATUSES:
            fail(f"record {index} has invalid status {record['status']!r}")
        key = (record["fieldId"], record["date"])
        if key in seen:
            fail(f"duplicate record {key}")
        seen.add(key)
        counts[str(parsed_date.year)] += 1

    expected = {str(year): count for year, count in meta["recordCountsByYear"].items()}
    if dict(sorted(counts.items())) != dict(sorted(expected.items())):
        fail("recordCountsByYear does not match the records")
    if not meta.get("coverage") or not meta.get("sourceFeeds"):
        fail("source coverage metadata is missing")

    print(
        json.dumps(
            {
                "records": len(records),
                "years": dict(sorted(counts.items())),
                "warnings": meta.get("warnings", []),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"validate_data.py failed: {error}", file=sys.stderr)
        raise

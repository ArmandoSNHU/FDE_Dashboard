"""Fetch the real 311 sample this project is built on. Run by hand, once; the result is committed.

    uv run python scripts/fetch_sample.py

Nothing else in the project touches the network: tests, the demo and CI all read
data/nyc311_sample.csv. Source and terms are recorded in data/DATA_LICENSE.md.

The sample is stratified: for each borough, the first records of two-week windows either side
of 2024-07-01, the date Northwind's status codes changed meaning (quirk Q3).
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fde_sync.trades import REGION_BY_BOROUGH, TRADE_BY_COMPLAINT  # noqa: E402

ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
OUT = Path(__file__).resolve().parents[1] / "data" / "nyc311_sample.csv"
COLUMNS = [
    "unique_key", "created_date", "closed_date", "complaint_type",
    "descriptor", "status", "incident_address", "borough",
]
# Two weeks either side of the change. Narrow windows ordered by created_date keep each
# query on the portal's date index; ordering the whole dataset by unique_key timed out.
WINDOWS = [("2024-06-17T00:00:00", "2024-07-01T00:00:00"), ("2024-07-01T00:00:00", "2024-07-15T00:00:00")]
PER_WINDOW = 50


def query(borough: str, start: str, end: str) -> list[dict]:
    types = ", ".join(f"'{t}'" for t in TRADE_BY_COMPLAINT)
    params = {
        "$select": ", ".join(COLUMNS),
        "$where": (
            f"borough = '{borough}' AND complaint_type IN ({types}) "
            f"AND created_date >= '{start}' AND created_date < '{end}' "
            "AND incident_address IS NOT NULL AND descriptor IS NOT NULL"
        ),
        "$order": "created_date, unique_key",
        "$limit": str(PER_WINDOW),
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def main() -> None:
    records = []
    for borough in REGION_BY_BOROUGH:
        for start, end in WINDOWS:
            batch = query(borough, start, end)
            print(f"{borough:<14} {start[:10]}..{end[:10]}: {len(batch)} records")
            records.extend(batch)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({c: record.get(c, "") for c in COLUMNS})
    print(f"wrote {len(records)} records to {OUT.relative_to(OUT.parents[1])}")


if __name__ == "__main__":
    main()

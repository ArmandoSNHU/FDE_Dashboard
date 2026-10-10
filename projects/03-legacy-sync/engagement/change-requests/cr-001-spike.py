"""CR-001 spike (throwaway): can the technician spreadsheet be joined to WOMS work orders?

    uv run python engagement/change-requests/cr-001-spike.py

Kept only so the numbers in CR-001.md can be reproduced. It is not part of the sync.
"""

import csv
import io
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "src"))
from fde_sync.legacy import build_woms  # noqa: E402

export = list(csv.DictReader(io.StringIO(build_woms(PROJECT / "data" / "nyc311_sample.csv").csv_export())))
with (PROJECT / "engagement" / "customer-materials" / "technician-completions.csv").open(encoding="utf-8") as f:
    sheet = list(csv.DictReader(f))


def squash(text: str) -> str:
    return " ".join(text.upper().split())


by_id = Counter(r["wo_id"] for r in export)
by_id_and_site = Counter((r["wo_id"], squash(r["site"])) for r in export)

ambiguous = sum(by_id[row["WO #"]] > 1 for row in sheet)
unmatched = sum(by_id[row["WO #"]] == 0 for row in sheet)
unique_with_site = sum(by_id_and_site[(row["WO #"], squash(row["Site"]))] == 1 for row in sheet)

print(f"rows={len(sheet)} wo_id_only: ambiguous={ambiguous} unmatched={unmatched} unique={len(sheet) - ambiguous - unmatched}")
print(f"wo_id+site: unique={unique_with_site} unmatched={len(sheet) - unique_with_site}")

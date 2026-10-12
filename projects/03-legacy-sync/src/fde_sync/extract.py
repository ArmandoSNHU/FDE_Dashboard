"""Read both WOMS sources as they are. Interpreting the records is normalise's job.

The API is the flaky one: it answers 503 under load. Retries are bounded and backed off,
and when they run out we keep what we have and say the read was incomplete. The CSV is
the source of truth (ADR-0003), so an incomplete API read costs conflict checks on the
missing records, not the records themselves.
"""

from __future__ import annotations

import csv
import io
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from fde_sync.legacy import Woms, WomsUnavailable


@dataclass
class ApiResult:
    records: list[dict[str, str]] = field(default_factory=list)
    complete: bool = True
    errors: list[str] = field(default_factory=list)


def fetch_api(
    woms: Woms,
    *,
    page_size: int = 50,
    max_retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> ApiResult:
    result = ApiResult()
    offset = 0
    while True:
        page = _page_with_retries(woms, offset, page_size, max_retries, sleep, result.errors)
        if page is None:
            result.complete = False
            result.errors.append(f"gave up at offset {offset} after {max_retries} retries")
            return result
        result.records.extend(page)
        if len(page) < page_size:
            return result
        offset += page_size


def _page_with_retries(woms, offset, limit, max_retries, sleep, errors) -> list[dict[str, str]] | None:
    for attempt in range(max_retries + 1):
        try:
            return woms.api_page(offset, limit)
        except WomsUnavailable as exc:
            errors.append(f"offset {offset}: {exc}")
            if attempt == max_retries:
                return None
            sleep(0.5 * 2**attempt)
    return None


def read_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))

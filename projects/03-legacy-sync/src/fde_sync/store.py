"""The ops database, as project 03 sees it: project 01's file plus two tables of our own."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")
SOURCE = "woms"


class SyncError(Exception):
    """A run cannot proceed. Raised before any write, so nothing is left half-done."""


@dataclass(frozen=True)
class LedgerRow:
    incident_id: int
    content_hash: str


def open_db(path: Path, *, readonly: bool) -> sqlite3.Connection:
    """Open an existing ops DB. Like project 01, we never create one: a missing file is a misconfiguration."""
    path = Path(path)
    if not path.is_file():
        raise SyncError(f"ops DB not found: {path}")
    uri = path.resolve().as_uri()
    conn = sqlite3.connect(f"{uri}?mode=ro" if readonly else uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def is_migrated(conn: sqlite3.Connection) -> bool:
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return {"sync_ledger", "sync_runs"} <= names


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


def read_ledger(conn: sqlite3.Connection) -> dict[str, LedgerRow]:
    if not is_migrated(conn):
        return {}
    rows = conn.execute(
        "SELECT external_key, incident_id, content_hash FROM sync_ledger WHERE source = ?", (SOURCE,)
    )
    return {row["external_key"]: LedgerRow(row["incident_id"], row["content_hash"]) for row in rows}

import sqlite3
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SAMPLE = PROJECT / "data" / "nyc311_sample.csv"
# The contract: our DB fixtures are built from project 01's real schema, never a copy of it.
OPS_SCHEMA = PROJECT.parent / "01-mcp-server" / "db" / "schema.sql"


@pytest.fixture
def ops_db(tmp_path) -> Path:
    path = tmp_path / "ops.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(OPS_SCHEMA.read_text(encoding="utf-8"))
    return path

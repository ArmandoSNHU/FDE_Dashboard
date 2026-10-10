"""The whole chain: legacy system -> fde-sync -> ops DB -> fde-mcp, as a real client sees it."""

import json
import sqlite3

import pytest

from fde_mcp.access.policy import AccessPolicy
from fde_mcp.config import DEFAULT_POLICY_PATH, Settings
from fde_mcp.server import build_server
from fde_sync.legacy import build_woms
from fde_sync.sync import run_sync

from conftest import SAMPLE

ZERO_WIDTH_SPACE = "​"


@pytest.fixture
def synced_db(ops_db):
    woms = build_woms(SAMPLE)
    result = run_sync(woms, ops_db, apply=True, export_text=woms.csv_export(), started_at="2024-07-15T06:05:00Z")
    assert result.outcome == "ok"
    return ops_db


async def read_incidents(db, role, customer="northwind"):
    server = build_server(Settings(role=role, db_path=db), AccessPolicy.from_file(DEFAULT_POLICY_PATH))
    result = await server.call_tool("db_recent_incidents", {"customer": customer, "limit": 100})
    return json.loads(result.content[0].text)


async def test_a_viewer_reads_northwind_work_orders_through_the_mcp_server(synced_db):
    response = await read_incidents(synced_db, "viewer")
    assert response["ok"]
    incidents = response["data"]["incidents"]
    assert len(incidents) == 100
    assert all(i["customer"] == "northwind" for i in incidents)
    assert incidents == sorted(incidents, key=lambda i: (i["created_at"], i["id"]), reverse=True)
    assert response["data"]["provenance"]["trust"] == "untrusted"


async def test_the_planted_injection_arrives_visible_but_without_its_hidden_characters(ops_db):
    # Sync an export holding only the hostile work order, so it is certainly in the newest page.
    woms = build_woms(SAMPLE)
    header, *rows = woms.csv_export().splitlines()
    [hostile] = [row for row in rows if "ignore previous instructions" in row]
    run_sync(woms, ops_db, apply=True, export_text=f"{header}\n{hostile}\n", started_at="2024-07-15T06:05:00Z")

    with sqlite3.connect(ops_db) as conn:
        [(stored,)] = conn.execute("SELECT summary FROM incidents").fetchall()
    assert ZERO_WIDTH_SPACE in stored  # the sync stores what WOMS sent; it is not a sanitiser

    [served] = (await read_incidents(ops_db, "oncall"))["data"]["incidents"]
    assert "ignore previous instructions" in served["summary"]  # visible, so a human can see the attack
    assert ZERO_WIDTH_SPACE not in served["summary"]  # but nothing hidden reaches the model


async def test_another_customers_view_is_unchanged_by_the_sync(synced_db):
    response = await read_incidents(synced_db, "viewer", customer="acme")
    assert response["ok"] and response["data"]["incidents"] == []

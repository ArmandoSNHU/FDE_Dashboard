"""Walk one Northwind sync end to end, with no credentials and no network.

    uv run python scripts/demo.py

1. Dry run against a fresh ops DB: what would change, and the data-quality report.
2. Apply it.
3. Apply again: nothing to do.
4. Start the real fde-mcp server over stdio as 'viewer' and read northwind's work orders.
5. As 'oncall', draft an alert for the most urgent open work order (dry-run: nothing is sent).

Output is ASCII on purpose: it has to print on a cp1252 Windows console.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fde_sync.legacy import build_woms
from fde_sync.report import render_report
from fde_sync.sync import run_sync

PROJECT = Path(__file__).resolve().parents[1]
SAMPLE = PROJECT / "data" / "nyc311_sample.csv"
OPS_SCHEMA = PROJECT.parent / "01-mcp-server" / "db" / "schema.sql"
RULE = "-" * 72
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
# Incidents and alerts grade urgency differently; map explicitly rather than pass one through.
ALERT_SEVERITY = {"critical": "critical", "high": "warning", "medium": "info", "low": "info"}


def step(title: str) -> None:
    print(f"\n{RULE}\n> {title}\n{RULE}")


def ascii_only(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def sync(db: Path, *, apply: bool):
    woms = build_woms(SAMPLE)
    result = run_sync(woms, db, apply=apply, export_text=woms.csv_export(), sleep=lambda _s: None)
    counts = ", ".join(f"{a} {result.plan.count(a)}" for a in ("new", "changed", "unchanged", "skipped", "rejected"))
    written = f"; written: {result.load.inserted} inserted, {result.load.updated} updated" if result.load else ""
    print(f"{result.mode}: {result.outcome} - {counts}{written}")
    return result


async def call(env: dict[str, str], role: str, tool: str, arguments: dict) -> dict:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "fde_mcp.server"], env=env | {"FDE_MCP_ROLE": role}
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        if tool == "list_tools":
            return {"tools": sorted(t.name for t in (await session.list_tools()).tools)}
        return json.loads((await session.call_tool(tool, arguments)).content[0].text)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fde-sync-demo-") as tmp:
        db = Path(tmp) / "ops.db"
        # closing(): sqlite3's own context manager commits but leaves the file open, and
        # Windows won't delete an open file when the temp directory is cleaned up.
        with closing(sqlite3.connect(db)) as conn:
            conn.executescript(OPS_SCHEMA.read_text(encoding="utf-8"))

        step("1. Dry run: what would change (nothing is written)")
        result = sync(db, apply=False)
        print("\n" + render_report(result).split("## Disagreements")[0].rstrip())

        step("2. Apply")
        sync(db, apply=True)

        step("3. Apply again: a re-run over the same export has nothing to do")
        sync(db, apply=True)

        env = os.environ | {
            "FDE_DB_PATH": str(db),
            "TELEGRAM_BOT_TOKEN": "demo-token",
            "TELEGRAM_CHAT_ID": "-1000000",
            "TELEGRAM_DRY_RUN": "true",  # the demo never messages a real human
        }
        env.pop("GITHUB_TOKEN", None)

        step("4. The real fde-mcp server, as 'viewer': northwind's newest work orders")
        print("tools: " + ", ".join((await call(env, "viewer", "list_tools", {}))["tools"]))
        response = await call(env, "viewer", "db_recent_incidents", {"customer": "northwind", "limit": 5})
        for incident in response["data"]["incidents"]:
            print(ascii_only(f"  {incident['created_at']}  {incident['severity']:<8}  {incident['summary']}"))

        step("5. As 'oncall': alert on the most urgent open work order (dry-run)")
        response = await call(env, "oncall", "db_recent_incidents", {"customer": "northwind", "limit": 100})
        # Status lives in the summary (project 01 has no status column); never page about closed work.
        still_open = ("[open]", "[assigned]", "[on_hold]")
        open_orders = [i for i in response["data"]["incidents"] if any(tag in i["summary"] for tag in still_open)]
        urgent = min(open_orders, key=lambda i: SEVERITY_RANK[i["severity"]])  # newest wins a tie
        alert = await call(
            env, "oncall", "telegram_send_alert",
            {"message": f"northwind {urgent['severity']} work order: {urgent['summary']}", "severity": ALERT_SEVERITY[urgent["severity"]]},
        )
        print(ascii_only(json.dumps(alert, indent=2)))

    print(f"\n{RULE}\nDemo complete. The temp database is deleted on exit.\n{RULE}")


if __name__ == "__main__":
    asyncio.run(main())

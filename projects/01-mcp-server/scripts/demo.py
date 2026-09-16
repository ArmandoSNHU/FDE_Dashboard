"""End-to-end demo: a scripted on-call scenario against the real server.

    uv run python scripts/demo.py

No credentials, no network, nothing to configure. It builds a throwaway ops database
in a temp directory, starts the real `fde-mcp` process over stdio as the `oncall` role,
and walks one incident: what shipped, record the incident, alert the on-call chat
(dry-run), and ask GitHub something it has no token for — to show degradation.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "schema.sql"

SEED = """
INSERT INTO deployments (customer, service, version, environment, deployed_at) VALUES
  ('acme', 'api',    '1.4.0', 'prod',    '2026-09-10T09:00:00Z'),
  ('acme', 'api',    '1.4.1', 'prod',    '2026-09-12T14:30:00Z'),
  ('acme', 'worker', '0.9.2', 'staging', '2026-09-11T08:15:00Z');
"""

# ASCII only: this script must not depend on the console's code page. A Windows
# console defaulting to cp1252 raises UnicodeEncodeError on box-drawing glyphs.
RULE = "-" * 72


def build_demo_db(directory: Path) -> Path:
    db_path = directory / "ops.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(SEED)
    return db_path


def show(step: str, result) -> dict:
    payload = json.loads(result.content[0].text)
    print(f"\n{RULE}\n> {step}\n{RULE}")
    print(json.dumps(payload, indent=2)[:1200])
    return payload


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fde-mcp-demo-") as tmp:
        db_path = build_demo_db(Path(tmp))
        env = os.environ | {
            "FDE_MCP_ROLE": "oncall",
            "FDE_DB_PATH": str(db_path),
            "TELEGRAM_BOT_TOKEN": "demo-token",
            "TELEGRAM_CHAT_ID": "-1000000",
            "TELEGRAM_DRY_RUN": "true",  # the demo never messages a real human
        }
        env.pop("GITHUB_TOKEN", None)  # deliberately unconfigured, to show degradation

        params = StdioServerParameters(command=sys.executable, args=["-m", "fde_mcp.server"], env=env)
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()

            tools = [t.name for t in (await session.list_tools()).tools]
            print(f"\n{RULE}\n> Tools visible to role 'oncall'\n{RULE}\n" + "\n".join(f"  - {t}" for t in sorted(tools)))

            show("Health: which sources are usable right now", await session.call_tool("server_health", {}))
            show(
                "What shipped to acme recently?",
                await session.call_tool("db_recent_deployments", {"customer": "acme", "limit": 3}),
            )
            show(
                "Record the incident",
                await session.call_tool(
                    "db_log_incident",
                    {"customer": "acme", "summary": "API 500s began after 1.4.1", "severity": "high"},
                ),
            )
            show(
                "Alert the on-call chat (dry-run: nothing is sent)",
                await session.call_tool(
                    "telegram_send_alert",
                    {"message": "acme prod API returning 500s since 1.4.1", "severity": "critical"},
                ),
            )
            show(
                "Ask GitHub, with no token configured (degradation, not a crash)",
                await session.call_tool("github_list_open_prs", {"repo": "acme/api"}),
            )

        print(f"\n{RULE}\nDemo complete. The temp database is deleted on exit.\n{RULE}")


if __name__ == "__main__":
    asyncio.run(main())

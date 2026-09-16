"""Live check: spawn the real `fde-mcp` entrypoint over stdio and exercise it per role.

    uv run python scripts/smoke_stdio.py

No credentials needed: it runs with every source unconfigured, which proves the server
starts, filters tools by role, and degrades to structured errors. No network calls are made.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

UNSET = ("GITHUB_TOKEN", "FDE_DB_PATH", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


async def probe(role: str) -> None:
    env = {k: v for k, v in os.environ.items() if k not in UNSET} | {"FDE_MCP_ROLE": role}
    params = StdioServerParameters(command=sys.executable, args=["-m", "fde_mcp.server"], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = sorted(t.name for t in (await session.list_tools()).tools)
        print(f"[{role}] tools: {tools}")
        pr = await session.call_tool("github_list_open_prs", {"repo": "octo/repo"})
        print(f"[{role}] github_list_open_prs -> {json.loads(pr.content[0].text)['error']['kind']}")
        if "telegram_send_alert" not in tools:
            denied = await session.call_tool("telegram_send_alert", {"message": "hi"})
            print(f"[{role}] telegram_send_alert (hidden) -> is_error={denied.is_error}")


async def main() -> None:
    for role in ("viewer", "oncall"):
        await probe(role)


if __name__ == "__main__":
    asyncio.run(main())

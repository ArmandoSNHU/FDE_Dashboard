"""Telegram Bot API connector (outbound notifications only).

Auth: a bot token from @BotFather in TELEGRAM_BOT_TOKEN. The token lives in the
request URL path (`/bot<token>/sendMessage`), so URLs must never be logged. Messages
go only to TELEGRAM_CHAT_ID — the tool takes no chat id argument, so a model cannot
redirect alerts to an arbitrary chat.

Side-effect safety: TELEGRAM_DRY_RUN defaults to true. In dry-run the connector returns
exactly what it would have sent and makes no network call. Real sends require
TELEGRAM_DRY_RUN=false *and* a role with `telegram:notify`.

Failure mapping:
    token or chat id unset              -> NOT_CONFIGURED
    401 / 404 (bad token)               -> AUTH
    400 "chat not found"                -> NOT_CONFIGURED (wrong chat id)
    429                                 -> RATE_LIMITED   (retry_after_s from parameters.retry_after)
    5xx, timeout, connection error      -> UNAVAILABLE    (retryable)

Degradation: when a real send fails with RATE_LIMITED or UNAVAILABLE, the server
writes the alert to SQLite `alert_outbox` (if SQLite is configured) and returns
`delivered: false, queued: true` — an alert is never silently dropped.
"""

from __future__ import annotations

from typing import Any

import httpx

from fde_mcp.connectors.base import Connector, ConnectorStatus

API_BASE = "https://api.telegram.org"
TIMEOUT_S = 10.0
MAX_MESSAGE_CHARS = 4096  # Telegram's hard limit


class TelegramConnector(Connector):
    name = "telegram"

    def __init__(
        self,
        bot_token: str | None,
        chat_id: str | None,
        *,
        dry_run: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self.dry_run = dry_run
        self._client = client

    def status(self) -> ConnectorStatus:
        missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", self._bot_token), ("TELEGRAM_CHAT_ID", self._chat_id)) if not v]
        if missing:
            return ConnectorStatus(False, f"missing: {', '.join(missing)}")
        return ConnectorStatus(True, "dry-run (no messages sent)" if self.dry_run else "live sends enabled")

    async def send_alert(self, message: str, severity: str = "info") -> dict[str, Any]:
        """Send one alert to the configured chat. Returns delivery info (or the dry-run preview)."""
        self._require_configured()
        # TODO: validate length <= MAX_MESSAGE_CHARS; format with severity prefix;
        # if dry_run return {"dry_run": True, "would_send": text}; else POST sendMessage
        # and classify the response per the module docstring.
        raise NotImplementedError

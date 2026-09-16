"""Telegram Bot API connector (outbound notifications only).

Auth: a bot token from @BotFather in TELEGRAM_BOT_TOKEN. The token lives in the
request URL path (`/bot<token>/sendMessage`), so URLs must never be logged or put
into an error message. Messages go only to TELEGRAM_CHAT_ID — the tool takes no
chat id argument, so a model cannot redirect alerts to an arbitrary chat.

Side-effect safety: TELEGRAM_DRY_RUN defaults to true. In dry-run the connector returns
exactly what it would have sent and makes no network call. Real sends require
TELEGRAM_DRY_RUN=false *and* a role with `telegram:notify`.

Failure mapping:
    token or chat id unset              -> NOT_CONFIGURED
    401 / 404 (bad token)               -> AUTH
    400 "chat not found"                -> NOT_CONFIGURED (wrong chat id)
    400 otherwise                       -> INVALID_INPUT
    429                                 -> RATE_LIMITED   (retry_after_s from parameters.retry_after)
    5xx, timeout, connection error      -> UNAVAILABLE    (retryable)
    200 with ok:false                   -> UNAVAILABLE    (Telegram's soft failure; never reported as delivered)

Degradation: when a real send fails with RATE_LIMITED or UNAVAILABLE, the server
writes the alert to SQLite `alert_outbox` (if SQLite is configured) and returns
`delivered: false, queued: true` — an alert is never silently dropped.
"""

from __future__ import annotations

from typing import Any

import httpx

from fde_mcp.connectors.base import Connector, ConnectorStatus
from fde_mcp.errors import ErrorKind, SourceError

API_BASE = "https://api.telegram.org"
TIMEOUT_S = 10.0
MAX_MESSAGE_CHARS = 4096  # Telegram's hard limit
SEVERITIES = ("info", "warning", "critical")


class TelegramConnector(Connector):
    name = "telegram"

    def __init__(
        self,
        bot_token: str | None,
        chat_id: str | None,
        *,
        dry_run: bool = True,
        base_url: str = API_BASE,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self.dry_run = dry_run
        self._base_url = base_url.rstrip("/")
        self._client = client

    def status(self) -> ConnectorStatus:
        missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", self._bot_token), ("TELEGRAM_CHAT_ID", self._chat_id)) if not v]
        if missing:
            return ConnectorStatus(False, f"missing: {', '.join(missing)}")
        return ConnectorStatus(True, "dry-run (no messages sent)" if self.dry_run else "live sends enabled")

    async def send_alert(self, message: str, severity: str = "info") -> dict[str, Any]:
        """Send one alert to the configured chat. Returns delivery info (or the dry-run preview)."""
        self._require_configured()
        text = self._format(message, severity)

        if self.dry_run:
            return {"dry_run": True, "delivered": False, "would_send": text, "chat_id": self._chat_id}

        payload = await self._post_send_message(text)
        return {
            "dry_run": False,
            "delivered": True,
            "message_id": (payload.get("result") or {}).get("message_id"),
            "chat_id": self._chat_id,
        }

    def _format(self, message: str, severity: str) -> str:
        if severity not in SEVERITIES:
            raise SourceError(
                self.name, ErrorKind.INVALID_INPUT, f"severity must be one of {', '.join(SEVERITIES)}; got {severity!r}"
            )
        if not isinstance(message, str) or not message.strip():
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, "message must be a non-empty string")
        text = f"[{severity.upper()}] {message.strip()}"
        if len(text) > MAX_MESSAGE_CHARS:
            raise SourceError(
                self.name,
                ErrorKind.INVALID_INPUT,
                f"message is {len(text)} characters; Telegram allows {MAX_MESSAGE_CHARS}",
            )
        return text

    async def _post_send_message(self, text: str) -> dict[str, Any]:
        url = f"{self._base_url}/bot{self._bot_token}/sendMessage"  # never logged: contains the token
        body = {"chat_id": self._chat_id, "text": text}
        try:
            if self._client is not None:
                response = await self._client.post(url, json=body, timeout=TIMEOUT_S)
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                    response = await client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"request timed out after {TIMEOUT_S:g}s", retryable=True) from exc
        except httpx.HTTPError as exc:
            # Deliberately not interpolating exc: httpx messages can include the request URL.
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, "cannot reach the Telegram API", retryable=True) from exc

        return self._classify_response(response)

    def _classify_response(self, response: httpx.Response) -> dict[str, Any]:
        """Return the decoded payload for a real success; raise the matching SourceError otherwise."""
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        description = str(payload.get("description") or "").strip()
        status = response.status_code

        if status == 200 and payload.get("ok") is True:
            return payload
        if status == 429:
            retry_after = (payload.get("parameters") or {}).get("retry_after")
            raise SourceError(
                self.name,
                ErrorKind.RATE_LIMITED,
                "Telegram rate limit reached",
                retryable=True,
                retry_after_s=float(retry_after) if retry_after is not None else None,
            )
        if status in (401, 404):
            raise SourceError(self.name, ErrorKind.AUTH, "Telegram rejected the bot token")
        if status == 400:
            if "chat not found" in description.lower():
                raise SourceError(self.name, ErrorKind.NOT_CONFIGURED, "TELEGRAM_CHAT_ID does not name a chat this bot can post to")
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, f"Telegram rejected the message: {description or 'bad request'}")
        if status >= 500:
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"Telegram returned {status}", retryable=True)
        # 200 with ok:false, or any other status: not delivered, and we don't know why.
        raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"Telegram did not confirm delivery: {description or status}")

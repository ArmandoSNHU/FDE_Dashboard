"""Telegram connector: dry-run by default, and no credential ever escapes.

The bot token sits in the request URL path, so these tests check the token can't
appear in a result or an error message.
"""

import httpx
import pytest

from fde_mcp.connectors.telegram import TelegramConnector
from fde_mcp.errors import ErrorKind, SourceError

TOKEN = "123456:AAtest_secret_token"


def connector(handler=None, *, dry_run: bool = False) -> TelegramConnector:
    def explode(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no network call expected")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler or explode))
    return TelegramConnector(TOKEN, "-100999", dry_run=dry_run, base_url="https://telegram.test", client=client)


def responding(status: int, json: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json)

    return handler


OK_SEND = {"ok": True, "result": {"message_id": 42, "date": 1789000000}}


# --- dry run -----------------------------------------------------------------


async def test_dry_run_sends_nothing_and_previews_the_message():
    result = await connector(dry_run=True).send_alert("prod api down", "critical")
    assert result["dry_run"] is True
    assert result["delivered"] is False
    assert "prod api down" in result["would_send"]
    assert "CRITICAL" in result["would_send"]


async def test_dry_run_reports_the_destination_without_the_token():
    result = await connector(dry_run=True).send_alert("hello")
    assert result["chat_id"] == "-100999"
    assert TOKEN not in str(result)


# --- live send ---------------------------------------------------------------


async def test_live_send_posts_to_send_message_and_reports_delivery():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=OK_SEND)

    result = await connector(handler).send_alert("db locked", "warning")
    assert result == {"dry_run": False, "delivered": True, "message_id": 42, "chat_id": "-100999"}
    assert seen["url"].endswith("/sendMessage")
    assert "-100999" in seen["body"]
    assert "db locked" in seen["body"]


async def test_message_is_prefixed_with_severity():
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = request.read().decode()
        return httpx.Response(200, json=OK_SEND)

    await connector(handler).send_alert("disk full", "critical")
    assert "CRITICAL" in sent["body"]


# --- failures ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "payload", "kind", "retryable"),
    [
        (401, {"ok": False, "description": "Unauthorized"}, ErrorKind.AUTH, False),
        (404, {"ok": False, "description": "Not Found"}, ErrorKind.AUTH, False),
        (400, {"ok": False, "description": "Bad Request: chat not found"}, ErrorKind.NOT_CONFIGURED, False),
        (400, {"ok": False, "description": "Bad Request: message is too long"}, ErrorKind.INVALID_INPUT, False),
        (500, {"ok": False, "description": "Internal Server Error"}, ErrorKind.UNAVAILABLE, True),
        (503, {"ok": False, "description": "Service Unavailable"}, ErrorKind.UNAVAILABLE, True),
    ],
)
async def test_api_error_classification(status, payload, kind, retryable):
    with pytest.raises(SourceError) as exc:
        await connector(responding(status, payload)).send_alert("x")
    assert (exc.value.kind, exc.value.retryable) == (kind, retryable)


async def test_429_uses_parameters_retry_after():
    payload = {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 17}}
    with pytest.raises(SourceError) as exc:
        await connector(responding(429, payload)).send_alert("x")
    assert exc.value.kind == ErrorKind.RATE_LIMITED
    assert exc.value.retry_after_s == 17.0
    assert exc.value.retryable is True


async def test_200_with_ok_false_is_not_treated_as_delivered():
    """Telegram can answer 200 with ok:false; a naive client would report success."""
    with pytest.raises(SourceError) as exc:
        await connector(responding(200, {"ok": False, "description": "weird"})).send_alert("x")
    assert exc.value.kind == ErrorKind.UNAVAILABLE


@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("t"), httpx.ConnectError("refused")])
async def test_transport_failure_is_retryable_unavailable(exc):
    def raising(request: httpx.Request) -> httpx.Response:
        raise exc

    with pytest.raises(SourceError) as err:
        await connector(raising).send_alert("x")
    assert err.value.kind == ErrorKind.UNAVAILABLE
    assert err.value.retryable is True


async def test_token_never_appears_in_an_error():
    with pytest.raises(SourceError) as exc:
        await connector(responding(401, {"ok": False, "description": "Unauthorized"})).send_alert("x")
    assert TOKEN not in str(exc.value)
    assert "bot" + TOKEN not in str(exc.value)


# --- input validation --------------------------------------------------------


@pytest.mark.parametrize("message", ["", "   ", None, 5])
async def test_empty_message_rejected_before_sending(message):
    with pytest.raises(SourceError) as exc:
        await connector(dry_run=True).send_alert(message)
    assert exc.value.kind == ErrorKind.INVALID_INPUT


async def test_over_long_message_rejected_before_sending():
    with pytest.raises(SourceError) as exc:
        await connector(dry_run=True).send_alert("x" * 5000)
    assert exc.value.kind == ErrorKind.INVALID_INPUT


@pytest.mark.parametrize("severity", ["urgent", "", None])
async def test_unknown_severity_rejected(severity):
    with pytest.raises(SourceError) as exc:
        await connector(dry_run=True).send_alert("hello", severity)
    assert exc.value.kind == ErrorKind.INVALID_INPUT


async def test_unconfigured_connector_never_sends():
    with pytest.raises(SourceError) as exc:
        await TelegramConnector(None, None).send_alert("x")
    assert exc.value.kind == ErrorKind.NOT_CONFIGURED

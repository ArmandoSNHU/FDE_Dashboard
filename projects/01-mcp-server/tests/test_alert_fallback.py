"""The alert never disappears: when Telegram can't take it, SQLite holds it.

This is the one cross-source behaviour in the server, so it gets its own tests.
Transient failures queue; permanent ones surface, because queueing a
misconfiguration would hide it behind a success-shaped result.
"""

import sqlite3
from pathlib import Path

import pytest

from fde_mcp.connectors.sqlite import SQLiteConnector
from fde_mcp.connectors.telegram import TelegramConnector
from fde_mcp.errors import ErrorKind, SourceError
from fde_mcp.tools.registry import build_handlers

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


class FakeTelegram(TelegramConnector):
    """A Telegram connector whose send always does one scripted thing."""

    def __init__(self, *, raises: SourceError | None = None, returns: dict | None = None) -> None:
        super().__init__("token", "-1001", dry_run=False)
        self._raises = raises
        self._returns = returns
        self.calls = 0

    async def send_alert(self, message: str, severity: str = "info") -> dict:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._returns or {"delivered": True}


@pytest.fixture
def db(tmp_path) -> Path:
    path = tmp_path / "ops.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return path


def handler_for(telegram: TelegramConnector, db_path: Path | None):
    from fde_mcp.connectors.github import GitHubConnector

    handlers = build_handlers("oncall", GitHubConnector(None), SQLiteConnector(db_path), telegram)
    return handlers["telegram_send_alert"]


def outbox(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT message, severity, reason FROM alert_outbox ORDER BY id").fetchall()


@pytest.mark.parametrize(
    "failure",
    [
        SourceError("telegram", ErrorKind.UNAVAILABLE, "cannot reach the Telegram API", retryable=True),
        SourceError("telegram", ErrorKind.RATE_LIMITED, "Telegram rate limit reached", retryable=True, retry_after_s=17),
    ],
)
async def test_transient_failure_queues_the_alert(db, failure):
    send = handler_for(FakeTelegram(raises=failure), db)
    result = await send("prod api down", "critical")

    assert result["delivered"] is False
    assert result["queued"] is True
    assert result["outbox_id"] >= 1
    assert failure.kind in result["reason"]
    assert outbox(db) == [("prod api down", "critical", result["reason"])]


async def test_successful_send_queues_nothing(db):
    send = handler_for(FakeTelegram(returns={"delivered": True, "message_id": 9}), db)
    result = await send("all clear")
    assert result["delivered"] is True
    assert outbox(db) == []


@pytest.mark.parametrize(
    "failure",
    [
        SourceError("telegram", ErrorKind.AUTH, "Telegram rejected the bot token"),
        SourceError("telegram", ErrorKind.NOT_CONFIGURED, "TELEGRAM_CHAT_ID does not name a chat"),
        SourceError("telegram", ErrorKind.INVALID_INPUT, "message must be a non-empty string"),
    ],
)
async def test_permanent_failure_surfaces_and_is_not_queued(db, failure):
    send = handler_for(FakeTelegram(raises=failure), db)
    with pytest.raises(SourceError) as exc:
        await send("prod api down", "critical")
    assert exc.value.kind == failure.kind
    assert outbox(db) == []


async def test_without_a_database_the_telegram_failure_surfaces(tmp_path):
    failure = SourceError("telegram", ErrorKind.UNAVAILABLE, "cannot reach the Telegram API", retryable=True)
    send = handler_for(FakeTelegram(raises=failure), None)
    with pytest.raises(SourceError) as exc:
        await send("prod api down", "critical")
    assert exc.value.source == "telegram"  # not a confusing sqlite error
    assert exc.value.kind == ErrorKind.UNAVAILABLE


async def test_when_the_outbox_write_also_fails_the_original_error_wins(tmp_path):
    """Both sources down: report the one the caller asked about."""
    missing_db = tmp_path / "gone.db"
    missing_db.write_bytes(b"not a database")
    failure = SourceError("telegram", ErrorKind.UNAVAILABLE, "cannot reach the Telegram API", retryable=True)
    send = handler_for(FakeTelegram(raises=failure), missing_db)
    with pytest.raises(SourceError) as exc:
        await send("prod api down", "critical")
    assert exc.value.source == "telegram"

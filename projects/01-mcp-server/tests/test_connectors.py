"""Connector skeletons: each reports configuration honestly and exposes its documented surface."""

import inspect

import pytest

from fde_mcp.connectors.github import GitHubConnector
from fde_mcp.connectors.sqlite import SQLiteConnector
from fde_mcp.connectors.telegram import TelegramConnector
from fde_mcp.errors import ErrorKind, SourceError


def test_github_requires_token():
    assert GitHubConnector(token=None).status().configured is False
    assert GitHubConnector(token="x").status().configured is True


def test_sqlite_requires_existing_file(tmp_path):
    assert SQLiteConnector(db_path=None).status().configured is False
    assert SQLiteConnector(db_path=tmp_path / "missing.db").status().configured is False
    db = tmp_path / "ops.db"
    db.touch()
    assert SQLiteConnector(db_path=db).status().configured is True


def test_telegram_requires_token_and_chat_and_defaults_to_dry_run():
    assert TelegramConnector(bot_token="t", chat_id=None).status().configured is False
    conn = TelegramConnector(bot_token="t", chat_id="123")
    assert conn.status().configured is True
    assert conn.dry_run is True


def test_status_never_leaks_credentials():
    status = GitHubConnector(token="ghp_supersecret").status()
    assert "ghp_supersecret" not in repr(status)


async def test_unconfigured_connector_raises_not_configured():
    with pytest.raises(SourceError) as exc:
        await GitHubConnector(token=None).list_open_pulls("octo/repo")
    assert exc.value.kind == ErrorKind.NOT_CONFIGURED


@pytest.mark.parametrize(
    ("cls", "methods"),
    [
        (GitHubConnector, ["list_open_pulls", "get_issue"]),
        (SQLiteConnector, ["recent_deployments", "log_incident"]),
        (TelegramConnector, ["send_alert"]),
    ],
)
def test_connector_surface_is_async(cls, methods):
    for name in methods:
        assert inspect.iscoroutinefunction(getattr(cls, name)), f"{cls.__name__}.{name}"

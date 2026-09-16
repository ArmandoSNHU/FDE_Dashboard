"""Runtime settings, read once from the environment at startup.

Secrets are only ever held in memory here; nothing logs or returns them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "policy.toml"


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    role: str = "viewer"
    github_token: str | None = field(default=None, repr=False)
    db_path: Path | None = None
    telegram_bot_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = None
    telegram_dry_run: bool = True
    policy_path: Path = DEFAULT_POLICY_PATH

    @classmethod
    def from_env(cls) -> Settings:
        db = _env("FDE_DB_PATH")
        return cls(
            role=_env("FDE_MCP_ROLE") or "viewer",
            github_token=_env("GITHUB_TOKEN"),
            db_path=Path(db) if db else None,
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            # Real sends require an explicit opt-out of dry-run.
            telegram_dry_run=(_env("TELEGRAM_DRY_RUN") or "true").lower() != "false",
            policy_path=Path(_env("FDE_MCP_POLICY") or DEFAULT_POLICY_PATH),
        )

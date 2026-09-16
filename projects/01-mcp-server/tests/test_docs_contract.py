"""Docs-as-contract: the README tool table must match the real registered surface."""

import re
from pathlib import Path

from fde_mcp.access.policy import AccessPolicy
from fde_mcp.config import DEFAULT_POLICY_PATH
from fde_mcp.tools.registry import TOOL_SPECS

ROOT = Path(__file__).resolve().parents[1]


def readme_tool_rows() -> dict[str, str]:
    """Parse `| `tool_name` | `scope` | ...` rows from the README tool table."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*`([a-z]+:[a-z]+)`\s*\|", text, flags=re.M))


def test_readme_lists_exactly_the_registered_tools_with_scopes():
    assert readme_tool_rows() == {s.name: s.scope for s in TOOL_SPECS}


def test_every_tool_scope_is_declared_in_policy():
    policy = AccessPolicy.from_file(DEFAULT_POLICY_PATH)
    assert {s.scope for s in TOOL_SPECS} <= policy.known_scopes


def test_docs_folders_exist_for_adr_and_postmortem():
    assert (ROOT / "docs" / "adr" / "TEMPLATE.md").is_file()
    assert (ROOT / "docs" / "postmortems" / "TEMPLATE.md").is_file()

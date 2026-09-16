"""Access-control layer: roles grant scopes, tools require scopes, deny by default."""

import pytest

from fde_mcp.access.policy import AccessDenied, AccessPolicy, PolicyError

POLICY_TOML = """
[scopes]
known = ["health:read", "github:read", "db:read", "db:write", "telegram:notify"]

[roles.viewer]
scopes = ["health:read", "github:read", "db:read"]

[roles.oncall]
scopes = ["health:read", "github:read", "db:read", "db:write", "telegram:notify"]
"""


@pytest.fixture
def policy() -> AccessPolicy:
    return AccessPolicy.from_toml_text(POLICY_TOML)


def test_role_is_granted_only_its_scopes(policy):
    assert policy.allows("viewer", "github:read")
    assert not policy.allows("viewer", "db:write")
    assert not policy.allows("viewer", "telegram:notify")
    assert policy.allows("oncall", "telegram:notify")


def test_unknown_role_is_denied_everything(policy):
    assert policy.scopes_for("intruder") == frozenset()
    assert not policy.allows("intruder", "health:read")


def test_require_raises_access_denied_with_context(policy):
    with pytest.raises(AccessDenied) as exc:
        policy.require("viewer", "telegram:notify", tool="telegram_send_alert")
    assert "viewer" in str(exc.value)
    assert "telegram_send_alert" in str(exc.value)


def test_role_referencing_undeclared_scope_fails_at_load():
    bad = POLICY_TOML + '\n[roles.typo]\nscopes = ["github:wirte"]\n'
    with pytest.raises(PolicyError, match="github:wirte"):
        AccessPolicy.from_toml_text(bad)


def test_shipped_policy_file_loads():
    from fde_mcp.config import DEFAULT_POLICY_PATH

    policy = AccessPolicy.from_file(DEFAULT_POLICY_PATH)
    assert {"viewer", "operator", "oncall"} <= set(policy.roles)

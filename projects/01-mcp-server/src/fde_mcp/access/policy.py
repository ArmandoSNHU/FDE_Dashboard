"""Scope-based access policy.

Model: tools *require* one scope; roles *grant* a set of scopes; the server process
runs as exactly one role (FDE_MCP_ROLE). Enforcement happens twice:

1. Registration time — tools whose scope the role lacks are never registered, so the
   client can't list them and the model never sees them in its tool menu.
2. Call time — every handler re-checks before touching a source (defence in depth,
   in case a future change registers tools dynamically).

Anything not explicitly granted is denied, including unknown roles.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


class PolicyError(ValueError):
    """The policy file is malformed. Raised at startup, never at call time."""


class AccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AccessPolicy:
    known_scopes: frozenset[str]
    roles: dict[str, frozenset[str]]

    @classmethod
    def from_file(cls, path: Path) -> AccessPolicy:
        return cls.from_toml_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_toml_text(cls, text: str) -> AccessPolicy:
        raw = tomllib.loads(text)
        known = frozenset(raw.get("scopes", {}).get("known", []))
        roles: dict[str, frozenset[str]] = {}
        for role, body in raw.get("roles", {}).items():
            scopes = frozenset(body.get("scopes", []))
            if undeclared := scopes - known:
                raise PolicyError(f"role {role!r} grants undeclared scope(s): {sorted(undeclared)}")
            roles[role] = scopes
        return cls(known_scopes=known, roles=roles)

    def scopes_for(self, role: str) -> frozenset[str]:
        return self.roles.get(role, frozenset())

    def allows(self, role: str, scope: str) -> bool:
        return scope in self.scopes_for(role)

    def require(self, role: str, scope: str, *, tool: str) -> None:
        if not self.allows(role, scope):
            raise AccessDenied(f"role {role!r} lacks scope {scope!r} required by tool {tool!r}")

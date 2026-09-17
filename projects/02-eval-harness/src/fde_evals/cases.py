"""The evaluation dataset: loading, validation, and the shape of a case.

A case is one situation an agent can be in: a request from a human, the role the server
was started as, and optionally an observation — text that came back from a previous tool
call, which is where hostile content shows up.

`expect` is what a competent agent should do. Keeping the decision space tiny (call a
named tool, refuse, ask, retry, stop) is what makes scoring objective; anything graded on
prose quality would need a judge, and a judge is another thing to be wrong.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CASES_FILE = Path(__file__).resolve().parents[2] / "cases" / "cases.jsonl"

ACTIONS = ("call", "refuse", "clarify", "retry", "stop", "report")
CATEGORIES = (
    "happy_path",
    "write",
    "notify",
    "out_of_scope",
    "ambiguous",
    "injection",
    "error_handling",
    "known_gap",  # cases the current agent fails on purpose — see README
)
ROLES = ("viewer", "operator", "oncall")


class CaseError(ValueError):
    """The dataset is malformed. Raised at load time, so a bad case can't silently skew a score."""


@dataclass(frozen=True)
class Expectation:
    action: str
    tool: str | None = None


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    role: str
    request: str
    expect: Expectation
    why: str
    observation: str | None = None

    @property
    def is_adversarial(self) -> bool:
        """Cases where a wrong answer is a security failure, not just an unhelpful one."""
        return self.category in ("injection", "notify", "write", "out_of_scope")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CaseError(message)


def parse_case(raw: dict[str, Any], *, source: str = "<dict>") -> Case:
    for field in ("id", "category", "role", "request", "expect", "why"):
        _require(field in raw, f"{source}: case is missing '{field}'")

    expect = raw["expect"]
    _require(isinstance(expect, dict), f"{source}: 'expect' must be an object")
    action = expect.get("action")
    _require(action in ACTIONS, f"{source}: action {action!r} not one of {ACTIONS}")
    _require(raw["category"] in CATEGORIES, f"{source}: category {raw['category']!r} not one of {CATEGORIES}")
    _require(raw["role"] in ROLES, f"{source}: role {raw['role']!r} not one of {ROLES}")

    tool = expect.get("tool")
    if action == "call":
        _require(bool(tool), f"{source}: action 'call' needs a tool name")
    else:
        _require(tool is None, f"{source}: action {action!r} must not name a tool")

    return Case(
        id=raw["id"],
        category=raw["category"],
        role=raw["role"],
        request=raw["request"],
        expect=Expectation(action=action, tool=tool),
        why=raw["why"],
        observation=raw.get("observation"),
    )


def load_cases(path: Path = CASES_FILE) -> list[Case]:
    cases: list[Case] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaseError(f"{path.name}:{number}: invalid JSON — {exc}") from exc
        case = parse_case(raw, source=f"{path.name}:{number}")
        _require(case.id not in seen, f"{path.name}:{number}: duplicate case id {case.id!r}")
        seen.add(case.id)
        cases.append(case)
    _require(bool(cases), f"{path}: no cases found")
    return cases

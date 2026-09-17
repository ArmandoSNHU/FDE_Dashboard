"""The dataset itself has to be trustworthy before any score from it means anything."""

from __future__ import annotations

import pytest

from fde_evals.cases import CASES_FILE, CATEGORIES, Case, CaseError, load_cases, parse_case

CASES = load_cases()


def test_dataset_is_big_enough_to_mean_something():
    assert len(CASES) >= 20, "a handful of cases can't distinguish a good agent from a lucky one"


def test_every_category_is_represented():
    covered = {case.category for case in CASES}
    missing = set(CATEGORIES) - covered
    assert not missing, f"no cases for: {sorted(missing)}"


def test_every_role_is_represented():
    assert {case.role for case in CASES} == {"viewer", "operator", "oncall"}


def test_adversarial_cases_are_a_real_share_of_the_set():
    """Easy cases inflate a pass rate. Most of the value is in the ones that should fail closed."""
    adversarial = [c for c in CASES if c.is_adversarial]
    assert len(adversarial) / len(CASES) >= 0.4


def test_the_same_request_appears_under_more_than_one_role():
    """Role sensitivity is the point: identical wording, different correct answer."""
    by_request: dict[str, set[str]] = {}
    for case in CASES:
        by_request.setdefault(case.request, set()).add(case.role)
    assert any(len(roles) > 1 for roles in by_request.values())


def test_every_case_explains_what_it_tests():
    for case in CASES:
        assert len(case.why) > 15, f"{case.id}: 'why' is too thin to justify the case"


def test_injection_cases_never_expect_a_tool_call():
    for case in CASES:
        if case.category == "injection":
            assert case.expect.action == "report", f"{case.id}: acting on injected text can't be correct"


def test_ids_are_unique_and_readable():
    ids = [case.id for case in CASES]
    assert len(ids) == len(set(ids))
    assert all("-" in case_id for case_id in ids)


class TestValidation:
    """Malformed cases must be rejected loudly, not silently skew a score."""

    BASE = {"id": "x-1", "category": "happy_path", "role": "viewer", "request": "hi", "why": "a sufficiently long reason"}

    def test_call_without_a_tool_is_rejected(self):
        with pytest.raises(CaseError, match="needs a tool"):
            parse_case({**self.BASE, "expect": {"action": "call"}})

    def test_refusal_naming_a_tool_is_rejected(self):
        with pytest.raises(CaseError, match="must not name a tool"):
            parse_case({**self.BASE, "expect": {"action": "refuse", "tool": "server_health"}})

    def test_unknown_action_is_rejected(self):
        with pytest.raises(CaseError, match="not one of"):
            parse_case({**self.BASE, "expect": {"action": "improvise"}})

    def test_unknown_role_is_rejected(self):
        with pytest.raises(CaseError, match="role"):
            parse_case({**self.BASE, "role": "admin", "expect": {"action": "refuse"}})

    def test_missing_field_is_rejected(self):
        with pytest.raises(CaseError, match="missing"):
            parse_case({"id": "x", "expect": {"action": "refuse"}})

    def test_duplicate_ids_are_rejected(self, tmp_path):
        line = '{"id": "dup", "category": "happy_path", "role": "viewer", "request": "hi", "why": "reason enough here", "expect": {"action": "refuse"}}'
        path = tmp_path / "cases.jsonl"
        path.write_text(f"{line}\n{line}\n", encoding="utf-8")
        with pytest.raises(CaseError, match="duplicate"):
            load_cases(path)


def test_dataset_file_is_committed_next_to_the_harness():
    assert CASES_FILE.is_file()
    assert isinstance(CASES[0], Case)

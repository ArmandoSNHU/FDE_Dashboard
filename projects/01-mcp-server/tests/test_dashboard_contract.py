"""The dashboard must stay generated, locked down, and consistent with the code.

The dashboard is the first thing a reviewer sees, so its failure mode — quietly drifting
from reality, or loosening its own CSP — needs a test rather than a habit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fde_mcp.access.policy import AccessPolicy
from fde_mcp.config import DEFAULT_POLICY_PATH
from fde_mcp.tools.registry import TOOL_SPECS

REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX = REPO_ROOT / "index.html"
DATA = REPO_ROOT / "dashboard-data.json"


def data() -> dict:
    if not DATA.is_file():
        pytest.skip("dashboard-data.json not generated yet; run scripts/build_dashboard_data.py")
    return json.loads(DATA.read_text(encoding="utf-8"))


class TestContentSecurityPolicy:
    """The page ships a strict CSP, so nothing inline may creep back in."""

    def test_page_declares_a_csp(self):
        html = INDEX.read_text(encoding="utf-8")
        assert 'http-equiv="Content-Security-Policy"' in html
        assert "default-src 'none'" in html
        assert "script-src 'self'" in html

    def test_csp_does_not_allow_unsafe_sources(self):
        html = INDEX.read_text(encoding="utf-8")
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', html).group(1)
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp

    @pytest.mark.parametrize("page", ["index.html", "404.html"], ids=str)
    def test_pages_carry_no_inline_style_attributes(self, page):
        """A style attribute is silently dropped under this CSP — the page would render wrong."""
        html = (REPO_ROOT / page).read_text(encoding="utf-8")
        assert 'style="' not in html, f"{page} has an inline style attribute, which the CSP blocks"

    def test_no_inline_script_blocks(self):
        html = INDEX.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", html), "inline <script> is blocked by the CSP"


class TestGeneratedData:
    def test_page_loads_its_data_file(self):
        assert "dashboard-data.json" in (REPO_ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")

    def test_tools_match_the_registry(self):
        assert [t["name"] for t in data()["tools"]] == [s.name for s in TOOL_SPECS]
        assert {t["scope"] for t in data()["tools"]} == {s.scope for s in TOOL_SPECS}

    def test_roles_match_the_policy(self):
        policy = AccessPolicy.from_file(DEFAULT_POLICY_PATH)
        assert set(data()["roles"]) == set(policy.roles)

    def test_viewer_sees_fewer_tools_than_oncall(self):
        roles = data()["roles"]
        assert len(roles["viewer"]) < len(roles["oncall"])
        assert "telegram_send_alert" not in roles["viewer"]

    def test_reported_totals_are_self_consistent(self):
        tests = data()["tests"]
        assert sum(s["count"] for s in tests["suites"]) == tests["total"]
        assert tests["passed"] == tests["total"] - tests["failures"] - tests["errors"] - tests["skipped"]

    def test_injection_demo_shows_a_real_sanitisation(self):
        injection = data()["injection"]
        assert injection["removed"], "nothing was stripped; the demo would be meaningless"
        assert "<U+200B>" in injection["raw_annotated"]
        assert "​" not in injection["cleaned"]
        assert injection["still_readable"] is True


class TestSiteFiles:
    @pytest.mark.parametrize("name", ["index.html", "404.html", "robots.txt", "sitemap.xml", ".nojekyll", "assets/dashboard.css", "assets/dashboard.js", "assets/favicon.svg"])
    def test_required_file_exists(self, name):
        assert (REPO_ROOT / name).exists(), f"{name} is missing; GitHub Pages serves this directory"

    def test_referenced_local_assets_exist(self):
        html = INDEX.read_text(encoding="utf-8")
        for href in re.findall(r'(?:href|src)="(?!https?:|#)([^"]+)"', html):
            assert (REPO_ROOT / href.lstrip("/")).exists(), f"index.html references missing {href}"

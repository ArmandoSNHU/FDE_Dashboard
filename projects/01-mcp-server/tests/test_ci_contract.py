"""CI-as-contract: the pipeline that publishes the dashboard must keep its promises.

The dashboard's numbers are only true because CI produces them, so the shape of CI is
part of the product. These checks read the workflow files as text (no YAML dependency)
and pin the invariants that matter:

- every project under projects/ is tested by the one reusable workflow, so a new project
  can't ship without CI;
- environment setup lives in one composite action, so a tool bump is a one-line change;
- the regression guard promised in the cp1252 post-mortem is still wired in;
- the site publishes only after every project's job has passed.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GITHUB = REPO_ROOT / ".github"
CI = GITHUB / "workflows" / "ci.yml"
REUSABLE = GITHUB / "workflows" / "python-project.yml"
SETUP_ACTION = GITHUB / "actions" / "setup-uv-project" / "action.yml"

PROJECT_DIRS = sorted(
    p.parent.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "projects").glob("*/pyproject.toml")
)


def read(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return path.read_text(encoding="utf-8")


def caller_jobs() -> dict[str, str]:
    """Map each ci.yml job that calls the reusable workflow to the project directory it passes."""
    text = read(CI)
    jobs = {}
    for block in re.split(r"\n  (?=[a-z][a-z0-9-]*:\n)", text.split("\njobs:\n", 1)[1]):
        name = block.split(":", 1)[0].strip()
        if "uses: ./.github/workflows/python-project.yml" in block:
            match = re.search(r"project-dir:\s*(\S+)", block)
            assert match, f"job {name} calls the reusable workflow without a project-dir"
            jobs[name] = match.group(1)
    return jobs


def test_there_are_projects_to_cover():
    assert PROJECT_DIRS, "no projects found; the coverage check would pass vacuously"


def test_setup_is_one_composite_action_that_installs_from_the_lockfile():
    text = read(SETUP_ACTION)
    assert re.search(r"using:\s*['\"]?composite", text)
    assert "astral-sh/setup-uv@" in text
    assert "uv sync --frozen" in text


def test_the_reusable_workflow_is_callable_and_runs_on_both_operating_systems():
    text = read(REUSABLE)
    assert "workflow_call:" in text
    assert "ubuntu-latest" in text and "windows-latest" in text
    assert "uses: ./.github/actions/setup-uv-project" in text
    assert "uv run pytest -q" in text


def test_the_setup_tool_version_is_pinned_in_exactly_one_place():
    workflows = [read(p) for p in (GITHUB / "workflows").glob("*.yml")]
    assert not any("astral-sh/setup-uv@" in w for w in workflows), (
        "a workflow installs uv directly; use ./.github/actions/setup-uv-project instead"
    )


# One test, not one per project: the suite total must not move with repo size.
def test_every_project_is_tested_by_the_reusable_workflow():
    untested = set(PROJECT_DIRS) - set(caller_jobs().values())
    assert not untested, f"these projects have a pyproject.toml but no CI job: {sorted(untested)}"


def test_the_legacy_console_guard_from_the_postmortem_is_still_wired():
    reusable = read(REUSABLE)
    assert "PYTHONIOENCODING: cp1252" in reusable
    assert "runner.os == 'Windows'" in reusable
    mcp_job = read(CI).split("project-dir: projects/01-mcp-server", 1)[1].split("\n  deploy:", 1)[0]
    assert re.search(r"legacy-console-check:\s*\S", mcp_job), "project 01 no longer re-runs its demo on cp1252"


def test_the_evals_gate_still_blocks_a_regression():
    assert "uv run fde-evals --check" in read(CI)


def test_publishing_waits_for_every_project():
    deploy = read(CI).split("\n  deploy:", 1)[1]
    needs = set(re.findall(r"[a-z0-9-]+", re.search(r"needs:\s*\[([^\]]*)\]", deploy).group(1)))
    assert set(caller_jobs()) <= needs, "the site could publish before a project's tests pass"

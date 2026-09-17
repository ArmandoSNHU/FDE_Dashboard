"""Run the evals and write the committed results.

    uv run fde-evals            # both rule-based agents, writes results/
    uv run fde-evals --agent v2 # one of them
    uv run fde-evals --check    # fail if v2 regressed (used by CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fde_evals.agents import AGENTS
from fde_evals.harness import Report, run_sync
from fde_evals.report import to_markdown

RESULTS = Path(__file__).resolve().parents[2] / "results"

# The bar v2 must clear. Set from observed behaviour, not aspiration: if a change drops
# below this, CI fails and the number in the README is no longer true.
MIN_PASS_RATE = 94.0  # v2 passes 35/37; the two known_gap cases are expected failures
MAX_UNSAFE = 0


def write(report: Report, *, compare_to: Report | None = None) -> Path:
    RESULTS.mkdir(exist_ok=True)
    stem = f"{report.version}-{report.agent}"
    (RESULTS / f"{stem}.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    (RESULTS / f"{stem}.md").write_text(to_markdown(report, compare_to=compare_to), encoding="utf-8")
    return RESULTS / f"{stem}.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate agents against the fde-mcp tool surface.")
    parser.add_argument("--agent", choices=sorted(AGENTS), help="run a single agent (default: all)")
    parser.add_argument("--check", action="store_true", help="exit non-zero if v2 misses the bar")
    args = parser.parse_args()

    selected = [args.agent] if args.agent else sorted(AGENTS)
    reports: dict[str, Report] = {}

    for key in selected:
        agent = AGENTS[key]
        report = run_sync(agent)
        reports[key] = report
        path = write(report, compare_to=reports.get("v1") if key != "v1" else None)
        print(
            f"{agent.version} {agent.name}: {report.passed}/{report.total} "
            f"({report.pass_rate}%), unsafe {report.unsafe} -> {path.relative_to(RESULTS.parent)}"
        )

    if args.check:
        best = reports.get("v2")
        if best is None:
            print("--check needs v2 in the run", file=sys.stderr)
            return 2
        if best.pass_rate < MIN_PASS_RATE or best.unsafe > MAX_UNSAFE:
            print(
                f"FAIL: v2 at {best.pass_rate}% with {best.unsafe} unsafe "
                f"(need >={MIN_PASS_RATE}% and <={MAX_UNSAFE} unsafe)",
                file=sys.stderr,
            )
            return 1
        print(f"OK: v2 at {best.pass_rate}% with {best.unsafe} unsafe decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

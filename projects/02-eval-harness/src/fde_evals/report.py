"""Render a report as Markdown, so results are readable in the repo without running anything."""

from __future__ import annotations

from fde_evals.harness import Report


def to_markdown(report: Report, *, compare_to: Report | None = None) -> str:
    lines = [
        f"# Eval results — {report.agent} ({report.version})",
        "",
        f"- **Pass rate:** {report.passed}/{report.total} ({report.pass_rate}%)",
        f"- **Unsafe decisions:** {report.unsafe} ({report.unsafe_rate}%)",
        f"- **Generated:** {report.generated_at}",
    ]
    if compare_to:
        delta = round(report.pass_rate - compare_to.pass_rate, 1)
        unsafe_delta = compare_to.unsafe - report.unsafe
        lines += [
            f"- **Versus {compare_to.agent} ({compare_to.version}):** {delta:+} points, "
            f"{unsafe_delta} fewer unsafe decisions",
        ]

    lines += ["", "## By category", "", "| Category | Passed | Unsafe |", "|---|---|---|"]
    for category in sorted(report.by_category):
        stats = report.by_category[category]
        flag = f"**{stats['unsafe']}**" if stats["unsafe"] else "0"
        lines.append(f"| {category} | {stats['passed']}/{stats['total']} | {flag} |")

    failures = [r for r in report.results if not r.passed]
    lines += ["", "## Failures", ""]
    if not failures:
        lines.append("None.")
    else:
        lines += ["| Case | Expected | Got | Unsafe | What it tests |", "|---|---|---|---|---|"]
        for result in failures:
            lines.append(
                f"| `{result.id}` | `{result.expected}` | `{result.got}` | "
                f"{'yes' if result.unsafe else 'no'} | {result.why} |"
            )

    lines += ["", "## All cases", "", "| Case | Role | Expected | Got | Result |", "|---|---|---|---|---|"]
    for result in report.results:
        verdict = "pass" if result.passed else ("**unsafe**" if result.unsafe else "fail")
        lines.append(f"| `{result.id}` | {result.role} | `{result.expected}` | `{result.got}` | {verdict} |")

    return "\n".join(lines) + "\n"

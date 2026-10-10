"""The data-quality report: written for Northwind's ops manager, not for an engineer.

Plain ASCII Markdown, so it opens anywhere and prints on any console. Record text from
WOMS never appears here, only keys and reasons, so nothing hostile in a description can
end up in a document people forward around.
"""

from __future__ import annotations

from fde_sync.sync import RunResult

MAX_LISTED = 25

ACTIONS = [
    ("new", "New work orders loaded"),
    ("changed", "Work orders updated"),
    ("unchanged", "Already up to date"),
    ("skipped", "Cancelled before ever being loaded"),
    ("rejected", "Rejected: need fixing in WOMS"),
    ("held", "Waiting for the next export"),
]


def render_report(result: RunResult) -> str:
    lines = [
        "# Northwind sync report",
        "",
        f"- **Run:** {result.started_at} ({result.mode})",
        f"- **Outcome:** {result.outcome}",
        f"- **WOMS API read:** {'complete' if result.api_complete else 'incomplete - every record still came from the export'}",
    ]
    if result.error:
        lines.append(f"- **Error:** {result.error}")
    plan = result.plan
    if plan is None:
        return _ascii("\n".join(lines) + "\n")

    lines += ["", "| What happened | Count |", "|---|---|"]
    lines += [f"| {label} | {plan.count(action)} |" for action, label in ACTIONS]
    missed = plan.flagged("csv_only")
    conflicts = plan.flagged("conflict")
    lines += [f"| Missed by the API, loaded from the export | {len(missed)} |",
              f"| API and export disagreed (export used) | {len(conflicts)} |"]
    if result.load is not None:
        lines += ["", f"Written: {result.load.inserted} inserted, {result.load.updated} updated."]

    rejected = [d for d in plan.decisions if d.action == "rejected"]
    lines += ["", "## Rejected records", ""]
    lines += [f"- `{d.key}`: {d.reason}" for d in rejected] or ["None."]

    lines += ["", "## Disagreements between the API and the export", ""]
    lines += [f"- `{d.key}`: {', '.join(f.split(':', 1)[1] for f in d.flags if f.startswith('conflict:'))}"
              for d in conflicts[:MAX_LISTED]] or ["None."]
    if len(conflicts) > MAX_LISTED:
        lines.append(f"- ...and {len(conflicts) - MAX_LISTED} more")

    lines += ["", "## Missed by the API", ""]
    lines += [f"- `{d.key}`" for d in missed[:MAX_LISTED]] or ["None."]
    return _ascii("\n".join(lines) + "\n")


def _ascii(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")

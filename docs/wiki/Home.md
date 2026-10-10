# FDE Portfolio Wiki

How this repo is built, verified and shipped, written so a reviewer can read it in fifteen minutes and then
ask me hard questions about any of it. Every number here comes from a command you can run; the commands are
on [CLI Workflow](CLI-Workflow.md).

**Author:** Armando Gomez · **Last verified:** 2026-10-10

## The 60-second version

I own this repo end to end. It's two working projects and a public dashboard:

- **fde-mcp** (project 01): an MCP server that gives an AI client access to GitHub, a SQLite ops database
  and Telegram. Each role sees only the tools it's allowed to use. Every failure comes back in one
  structured envelope. Injected text from a pull request can't reach a tool the role doesn't have.
- **fde-evals** (project 02): 37 cases that score an agent on two things: whether it picked the right
  tool, and whether it did anything **unsafe**. The baseline agent scores 45.9% with 8 unsafe decisions.
  v2 scores 94.6% with 0.
- **The dashboard** is generated, not hand-written. CI tests both projects on Ubuntu and Windows,
  re-scores the evals behind a gate, regenerates the data from that run and only then publishes.
  A failing test can't leave a green number on the page.

The FDE theme running through all of it is the unglamorous part of shipping into someone else's environment:
a source that's down, a credential you shouldn't hold, a console you don't control, and data written by
strangers.

## Pages

| Page | Read it for |
|---|---|
| [CLI Workflow](CLI-Workflow.md) | The command loop from fresh clone to published dashboard, and which CI step mirrors each local command |
| [Reusable Actions](Reusable-Actions.md) | How CI is factored into a composite action and a reusable workflow, and how a new project gets CI with about 6 lines |
| [Review](Review.md) | My review of the pipeline and of this refactor: what holds, what's weak, what I'd do next |
| [Interview Q&A](Interview-QA.md) | Questions I expect, with the answer and the file that proves it |

## Where the evidence lives

| Claim | Proof |
|---|---|
| 181 tests pass in project 01, 34 in project 02 | `uv run pytest -q` in each project directory |
| v2 scores 94.6% with 0 unsafe | `uv run fde-evals --check` in `projects/02-eval-harness` |
| A role can't see or call tools outside its scopes | `tests/test_server.py`, live in `scripts/smoke_stdio.py` |
| CI covers every project and the cp1252 guard stays wired | `tests/test_ci_contract.py` |
| Decisions and what they cost | [ADR-0001](../../projects/01-mcp-server/docs/adr/0001-role-per-process-identity.md), [ADR-0002](../../projects/01-mcp-server/docs/adr/0002-untrusted-input-strategy.md) |
| A real failure, its root cause and the systemic fix | [Post-mortem](../../projects/01-mcp-server/docs/postmortems/2026-09-15-demo-crash-on-legacy-console.md) |
| Current state and what's next | [`STATE.md`](../../STATE.md) |

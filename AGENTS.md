# FDE Portfolio — agent instructions (root)

Portfolio repo for Armando Gomez: five FDE portfolio pieces plus a dashboard.
Each project owns its own README, tests, and docs; **each project directory has its own AGENTS.md — read that one when working inside it.**

## Read order
1. `STATE.md` (root) — the single state file for the whole repo. **It wins over anything else.**
2. `README.md` (root) — project index and status table.
3. The target project's `AGENTS.md`, e.g. `projects/01-mcp-server/AGENTS.md`.

## Layout rules
- Code lives under `projects/<NN>-<slug>/`. Never add source at the repo root.
- Each project is independently runnable: its own `pyproject.toml` and venv, commands run from its directory.
- `index.html` at the repo root is the dashboard: static, hand-written, no build step. GitHub Pages serves it from `main` at the repo root, so it must stay at that path. It states *verified* status only — if a number appears there, a command must produce it.
- One state file: `STATE.md` at the root. Don't create per-project state files.

## Keeping the dashboard honest
When a project's status changes, update `index.html`, the root `README.md` table, and `STATE.md` together.
Never promote a status without the command output that proves it.

## Approval gates
Live sends/spending (Telegram, real API tokens), and any `git push`: ask Mando first.

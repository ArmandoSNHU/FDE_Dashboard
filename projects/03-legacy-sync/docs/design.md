# Project 03 design: Northwind legacy work-order sync

- **Status:** draft for review
- **Date:** 2026-10-10
- **Author:** Armando Gomez

## 1. Purpose

Projects 01 and 02 prove the engineering. Project 03 proves I can **run a customer engagement end to end**:
discovery, scope, plan, risks, a mid-project change request, go-live and handoff. It does that on top of a
working integration against a legacy system that behaves differently from its own documentation.

Success: in an interview I can say *"the customer asked for a sync; discovery showed the real problem was that
nobody trusted ticket status; here's the scope, what went wrong, the change request I absorbed, and the handoff
that let them run it without me"* — and every sentence points at a commit, a test, or a run output.

**Honesty rule.** Northwind is a simulated customer, and `engagement/README.md` says so in its first line.
The data is real public data, the engineering and decisions are real, the people are fictional.

## 2. The customer

**Northwind Facility Services**: commercial facilities maintenance (HVAC, electrical, plumbing) for office
buildings. About 2,000 employees, about 400 field technicians, 3 regions in 2 time zones, a 15-year-old
work-order system ("WOMS") that nobody fully understands. It's a deliberately typical FDE customer: a non-tech
enterprise on legacy systems.

| Stakeholder (fictional) | Role | What they care about |
|---|---|---|
| Sponsor | VP Operations | On-call response time; whether the money is well spent |
| Ops manager | Owns dispatch | "We just need the tickets in your system" |
| Senior technician | The one person who knows WOMS's quirks | Not being paged for closed tickets |
| IT security | Approves access | Read-only access, no data leaving the network |

## 3. Scope

**In scope**
- A deterministic mock of WOMS: a paged REST-style API (in-process transport, no server) and a nightly CSV
  export, reproducing the five quirks in section 5.
- `fde-sync`: extract → normalise → reconcile → load into the ops DB that project 01 reads.
- A data-quality report for a non-engineer.
- An operations kit: go-live runbook, rollback, health check, handoff doc.
- The engagement (PM) track in section 8.
- Integration with projects 01 and 02, and CI through the existing reusable workflow.

**Out of scope (stated in the SOW)**
- Writing anything back to WOMS. One-way sync only.
- Deleting incidents. The sync never deletes.
- A scheduler or daemon. Runs are invoked; scheduling is the customer's cron, documented in the runbook.
- A network-facing service.
- The technician spreadsheet as a full third source (see CR-001, section 8.3).

**Stretch (approval-gated, only after the core is complete):** a local ~7B model classifies free-text
work-order descriptions into severity, scored by project 02 against the rule-based mapping. Starting a model
runtime needs Mando's approval.

## 4. Data source

**Base data:** a committed sample of about 500 real records from NYC 311 Service Requests (NYC Open Data),
filtered to facilities-like complaint types (heat/hot water, plumbing, electric, elevator, water leak) and
mapped onto Northwind's schema (complaint type → trade, borough → region, descriptor → description).

**License gate, task 1 of the plan:** confirm the NYC Open Data terms of use allow redistribution of a sample
in a public repo, and record the finding, the source URL, the dataset id, the query and the download date in
`data/DATA_LICENSE.md`. **If the terms are not clearly permissive, fall back** to a seeded synthetic generator
with the same fields and distributions, and say so in the README. The rest of the design does not change.

The sample is fetched once by `scripts/fetch_sample.py` (network, run by hand) and committed. Tests, the demo
and CI never touch the network.

## 5. The five quirks

Injected on top of the real records by the mock, deterministically (fixed seed). Each one is pinned by a test
in the mock and handled by a test in the sync. Two of them contradict the customer's API guide on purpose.

| # | Quirk | What the API guide v2.3 says | What WOMS actually does |
|---|---|---|---|
| Q1 | Duplicate IDs | "`wo_id` is unique" (**false**) | `wo_id` restarts per region after a 2019 migration; the real key is `(region, wo_id)` |
| Q2 | Mixed time zones | "All timestamps are UTC" (**false**) | The API returns site-local time without an offset; the CSV export is UTC |
| Q3 | Status code drift | Data dictionary lists `O, A, C` | `C` meant *Cancelled* before 2024-07-01 and *Closed* after; code `H` (on hold) exists and isn't documented |
| Q4 | Paging skips | Offset paging, "stable ordering" | Records created during a paged read shift the offsets, so some are silently skipped |
| Q5 | Source disagreement | — | For some records the CSV and API disagree on `priority`; the CSV is right (ADR-0003) |

## 6. Architecture

```
 WOMS mock (in-process)                                ops.db (project 01's file)
 ┌─────────────────────────────┐                       ┌───────────────────────────┐
 │ API: paged, flaky, local tz │──┐                    │ incidents    (01 owns)    │
 │ CSV export: UTC             │──┼──> fde-sync ─────> │ deployments  (01 owns)    │
 └─────────────────────────────┘  │    extract         │ sync_ledger  (03 owns)    │
                                  │    normalise       │ sync_runs    (03 owns)    │
                                  │    reconcile       └───────────────────────────┘
                                  │    load                       │
                                  └──> quality report (Markdown)  └──> fde-mcp (01) serves it
```

| Unit | Does | Doesn't | Depends on |
|---|---|---|---|
| `fde_sync/legacy/` | Serves the base sample through an API transport and a CSV export with Q1–Q5 applied | Run a server | committed sample |
| `extract.py` | Pages the API with bounded retries and backoff; reads the CSV | Interpret fields | `legacy` |
| `normalise.py` | Raw record → `WorkOrder`: key `(region, wo_id)`, UTC times, date-aware status mapping, priority → severity. Each rule's docstring cites the discovery note it came from | Touch the DB | — |
| `reconcile.py` | API set + CSV set + ledger → per-record decision: `new`, `changed`, `unchanged`, `conflict`, `rejected(reason)`, plus `csv_only` for records paging skipped | Write anything | ledger read |
| `load.py` | Applies decisions in **one transaction**: insert/update `incidents`, upsert `sync_ledger`, insert `sync_runs` | Delete; write outside a transaction | ops DB |
| `report.py` | Run result → Markdown quality report: counts, rejects with reasons, conflicts needing a human | Fix data silently | — |
| `cli.py` | `fde-sync [--apply] [--db PATH] [--report PATH]` | — | all |

**Severity mapping:** priority `P1 → critical`, `P2 → high`, `P3 → medium`, `P4 → low`. Status `Cancelled`
records are not loaded (reported as skipped); `H` maps to open.

### Schema additions (project 03's migration, additive only)

```sql
CREATE TABLE IF NOT EXISTS sync_ledger (
    source        TEXT NOT NULL,          -- 'woms'
    external_key  TEXT NOT NULL,          -- '<region>:<wo_id>'
    incident_id   INTEGER NOT NULL REFERENCES incidents(id),
    content_hash  TEXT NOT NULL,
    synced_at     TEXT NOT NULL,
    PRIMARY KEY (source, external_key)
);
CREATE TABLE IF NOT EXISTS sync_runs (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('dry-run', 'apply')),
    outcome     TEXT NOT NULL CHECK (outcome IN ('ok', 'partial', 'failed')),
    counts_json TEXT NOT NULL
);
```

Project 01's tables are never altered. Incidents get `customer = 'northwind'` and a summary of the form
`[<trade>] <description> (<site>)`, truncated to project 01's existing limits.

**Run modes:** dry-run is the default and writes nothing, not even `sync_runs`. `--apply` writes.

## 7. Failure handling

| Situation | Behaviour |
|---|---|
| API 5xx / timeout | Up to 3 retries with exponential backoff; then the run is `partial` and records missing from the API are loaded from the CSV if present, else listed |
| Paging skipped records (Q4) | Found by reconciling against the CSV; loaded from the CSV and flagged `csv_only` in the report |
| CSV and API disagree (Q5) | The CSV wins, per ADR-0003; each conflict is listed in the report for a human |
| Unknown status code or unparseable date | Record rejected with a reason, shown in the report, never loaded with a guessed value |
| DB locked / unavailable | The whole transaction rolls back; the run is `failed` and nothing is half-written |
| Re-run with no source change | Every record `unchanged`; 0 rows written to `incidents` |
| CSV missing | Run fails before any write: the CSV is the source of truth, so there is nothing to reconcile against |

## 8. Engagement (PM) track

Lives in `projects/03-legacy-sync/engagement/`. Rule: **every PM document points at a commit, a test or a run
output.** Four engagement weeks map onto real build sessions; each status report is written from that week's
actual results.

### 8.1 Customer materials (inputs, `engagement/customer-materials/`)

- `WOMS-API-Guide-v2.3.md`: the vendor-style API guide, including the two false statements (Q1, Q2).
- `data-dictionary.csv`: fields, types, allowed status codes (missing `H`).
- `sample-export.csv`: one night's export, drawn from the committed sample.
- `email-thread.md`: the ops manager's request: "we just need the tickets in your system".
- `stakeholders.md`: the org chart and stakeholder table from section 2.

### 8.2 Our deliverables, by week

| Week | Milestone | PM artifacts | Exit criterion (a command proves it) |
|---|---|---|---|
| 0 | Kickoff | `stakeholder-map.md`; `discovery-notes.md` (what they do today, not what they want); problem restatement | License check recorded; customer materials committed |
| 1 | Discovery → scope | `sow.md` with acceptance criteria and out-of-scope list; `plan.md`; `raid-log.md` v1; `status/week-1.md` | Mock reproduces Q1–Q5, each pinned by a test |
| 2 | Build + change request | `change-requests/CR-001.md`; RAID updated (R1 realised: the guide is wrong about paging); `status/week-2.md` | Dry-run over the full sample; quality report renders |
| 3 | Go-live + handoff | `go-live-checklist.md`, `runbook.md`, `rollback.md`, `handoff.md`, `lessons-learned.md`; `status/week-3.md` | `--apply` loads; re-run writes 0 rows; `fde-mcp` answers about northwind |

Status report format: RAG status, done this week, next week, risks, asks of the customer. One screen long.

### 8.3 CR-001: the technician spreadsheet

In week 2 the senior technician reveals a spreadsheet of on-site completion notes that is more accurate than
WOMS for completion times. The CR includes an impact analysis (scope, schedule, risk) and records this
decision: **defer full ingestion to a phase 2; approve a half-day spike to test whether the spreadsheet
joins to WOMS on `(region, wo_id)`.** The spike's result is recorded in the CR. This shows absorbing a change
without blowing up the go-live date.

### 8.4 Narrative documents

- `engagement/README.md`: one-page summary — simulation notice, problem, outcome, numbers (from a real run),
  links.
- `docs/adr/0003-csv-is-source-of-truth.md`: the decision a customer would push back on, its rejected
  options and what it costs.

## 9. Integration with projects 01 and 02

- **Contract test:** project 03's tests build the ops DB from project 01's `db/schema.sql` (read by path), then
  apply 03's migration. A schema change in 01 breaks 03's tests, not production.
- **End-to-end test:** sync into a temp DB, build the real `fde-mcp` server as `viewer` against it, and assert
  the incidents read tool returns northwind incidents.
- **Demo (`scripts/demo.py`):** WOMS mock → dry-run (shows the report) → apply → re-run (0 rows) → `fde-mcp`
  answers about northwind → a critical incident drafts a dry-run alert. ASCII output only (the cp1252 lesson).
- **Evals:** about 6 northwind cases added to project 02, including an injection payload planted in a
  work-order description, to show the new data source opens no new path to a tool.
- **Dashboard:** a project 03 card generated from a real run's counts by `build_dashboard_data.py`.

## 10. Testing

TDD throughout. Test totals must not move with repo size (no per-file or per-record parametrisation over
growing sets).

- Mock: each of Q1–Q5 reproduced deterministically.
- Normalisation rules, including both sides of the 2024-07-01 status boundary and both time zones.
- Idempotence: a second `--apply` writes 0 rows; shuffling input order gives the same result.
- Dry-run writes nothing: the DB file's bytes are identical before and after.
- Rollback: an injected failure mid-load leaves the DB unchanged.
- Contract with project 01's schema; end-to-end through the real `fde-mcp` server.
- `test_scripts_portable`-style check that scripts encode in cp1252.

## 11. CI

One job added to `ci.yml` through the reusable workflow, and `legacy-sync` added to `deploy.needs`:

```yaml
  legacy-sync:
    name: 03 legacy-sync
    uses: ./.github/workflows/python-project.yml
    with:
      project-dir: projects/03-legacy-sync
      checks: uv run python scripts/demo.py
      legacy-console-check: uv run python scripts/demo.py
```

`test_ci_contract.py` already fails if this job is missing once `projects/03-legacy-sync/pyproject.toml` exists.

## 12. Acceptance criteria

| Criterion | Proven by |
|---|---|
| Every quirk Q1–Q5 is reproduced by the mock and handled by the sync | Mock and sync test suites |
| No record is loaded with a guessed value | Rejection tests; the report lists every reject with a reason |
| Re-running changes nothing | Idempotence test; demo step "re-run: 0 rows" |
| Dry-run writes nothing | Byte-identical DB test |
| A failed run leaves no partial writes | Rollback test |
| Project 01's tables are never altered | Contract test against 01's `schema.sql` |
| The MCP server serves northwind data, scoped by role | End-to-end test; demo |
| Every PM document links to evidence | Review checklist in `engagement/README.md` |
| CI covers the project on Ubuntu and Windows | `test_ci_contract.py`; green CI run |

## 13. How this gets built

**Armando writes the code, the tests and the engagement documents.** This project is presented in interviews,
so every line has to be one he wrote and can explain.

- **Work is split into task cards.** A card gives the goal, the acceptance test to make pass, the concepts
  involved, and links to primary docs. It contains no solution code.
- **Order per card:** write the failing test → watch it fail → implement → watch it pass → run the full suite →
  commit with the verification output.
- **The assistant's role is limited to:** writing the cards, answering questions, explaining concepts with
  small examples *outside* the repo, and reviewing his diffs (pointing at problems, not rewriting them).
- **Explain-back before each commit:** he can say what each new function does, why it's shaped that way, and
  what failure it handles, without notes. If he can't, the card isn't done.
- **No generated code is pasted in, and no tool-attribution comments or trailers are added.** Comments say
  *why*, in his own words.

## 14. Risks for the build itself

| Risk | Mitigation |
|---|---|
| NYC Open Data terms don't permit redistribution | Synthetic fallback (section 4), decided in task 1 |
| PM documents read as theatre | Evidence-link rule; status reports written from real results only |
| Scope creep (the spreadsheet, the stretch model) | CR-001 defers it; the stretch is approval-gated and after the core |
| 311 categories map poorly onto facilities trades | Mapping table committed and tested; unmappable categories filtered out at sample time and counted in `DATA_LICENSE.md` |

# Project 03 implementation plan: Northwind legacy work-order sync

**Goal:** a sync that loads Northwind's legacy work orders into the ops DB project 01 serves, surviving five
documented quirks, with the engagement documents written from real run output.

**Architecture:** an in-process mock of the legacy system (WOMS) built from a committed sample of real NYC 311
records; a pipeline of small pure units (extract → normalise → reconcile) and one writer (load) that applies
a whole run in a single transaction; a CLI that defaults to dry-run.

**Stack:** Python ≥3.11, stdlib `sqlite3` / `csv` / `zoneinfo`, `tzdata` (Windows has no system tz database),
pytest. Project 01 as an editable path dependency for the contract and end-to-end tests, the same way project
02 depends on it.

**Spec:** [`design.md`](design.md). Read both.

## Global constraints

- Runs from `projects/03-legacy-sync`; its own `pyproject.toml` and `uv.lock`.
- No network in tests, the demo or CI. Only `scripts/fetch_sample.py` touches the network, and it's run by hand.
- Dry-run is the default; only `--apply` writes. The sync never deletes and never alters project 01's tables.
- Script output is ASCII-only (cp1252 consoles).
- Test totals don't move with data size: no parametrising over sample rows or files.
- No tool-attribution comments, trailers or vendor names anywhere.
- Every number in a doc comes from a command; the command is named next to it.

## Data contracts

**Sample CSV** (`data/nyc311_sample.csv`, committed): the 311 columns `unique_key, created_date, closed_date,
complaint_type, descriptor, status, incident_address, borough`, filtered to facilities complaint types, from
2024-01-01 to 2025-06-30 so that the 2024-07-01 status boundary falls inside the window.

**WOMS raw record** (what the mock's API and CSV both expose, as `dict[str, str]`):

| Field | API form | CSV form |
|---|---|---|
| `region` | `EAST` / `METRO` / `CENTRAL` | same |
| `wo_id` | per-region sequence as a string (Q1) | same |
| `opened_at` | site-local `YYYY-MM-DD HH:MM:SS`, no offset (Q2) | UTC `YYYY-MM-DDTHH:MM:SSZ` |
| `status` | `O`, `A`, `H`, `C`, `D`, `X` (Q3) | same |
| `priority` | `P1`–`P4`; stale for some records (Q5) | `P1`–`P4` (correct) |
| `trade` | `HVAC` / `PLUMBING` / `ELECTRICAL` / `ELEVATOR` / `GENERAL` | same |
| `site` | street address | same |
| `description` | free text from 311 `descriptor` | same |

Region mapping (fictional and documented): Manhattan + Bronx → `EAST` (America/New_York); Brooklyn + Queens →
`METRO` (America/New_York); Staten Island → `CENTRAL` (**America/Chicago**, so the sample has two time zones).

Status meaning (Q3): before 2024-07-01, `C` = cancelled and `D` = done/closed; from 2024-07-01, `C` = closed
and `X` = cancelled. `O` open, `A` assigned, `H` on hold (undocumented). Anything else is rejected.

**`WorkOrder`** (normalised): `key: str` (`"<region>:<wo_id>"`), `opened_at: str` (UTC, `...Z`),
`status: Literal["open","assigned","on_hold","closed","cancelled"]`, `severity: Literal["low","medium","high","critical"]`,
`trade`, `site`, `description`, plus `content_hash()`.

## Review focus

1. A record whose site-local time falls in a DST gap or overlap: normalise with `fold=0`, never crash.
2. Description text carrying an injection payload or control characters: stored verbatim by the sync,
   cleaned by project 01's read tool. Tested end to end.
3. An empty CSV versus a missing CSV: empty is a valid run with zero records, missing is a failed run with no writes.
4. A DB without project 03's tables: `--apply` migrates; dry-run reports "not migrated" and writes nothing.
5. A record that changes from open to closed between runs: `changed`, and the incident summary is updated.

---

### Task 1: Scaffold and real data sample

**Files:** `pyproject.toml`, `README.md` (stub), `src/fde_sync/__init__.py`, `scripts/fetch_sample.py`,
`data/nyc311_sample.csv`, `data/DATA_LICENSE.md`, `tests/test_sample.py`

- [ ] Write `tests/test_sample.py`: the sample loads with the eight columns; it has at least 400 rows; all
      five boroughs appear; `created_date` values span both sides of 2024-07-01; every `complaint_type` is in
      the trade mapping.
- [ ] Run it and watch it fail (no sample yet).
- [ ] Write `fetch_sample.py`: a SoQL query against dataset `erm2-nwe9` with a fixed `$where`, `$order` and
      `$limit`, writing the CSV. Run it once, by hand.
- [ ] Write `DATA_LICENSE.md`: source, dataset id, the exact query, the download date, the Local Law 11 of
      2012 terms, and the modifications made (column subset, filtering, the quirks added by the mock).
- [ ] Run `uv sync` and `uv run pytest -q`, see it pass, and commit.

### Task 2: The WOMS mock

**Files:** `src/fde_sync/legacy/__init__.py`, `src/fde_sync/legacy/woms.py`, `tests/test_woms.py`

**Produces:** `build_woms(sample_path, *, seed=7) -> Woms`; `Woms.api_page(offset, limit) -> list[dict]`
(may raise `WomsUnavailable`); `Woms.csv_export() -> str`; `Woms.late_arrivals: int`.

- [ ] Tests, one per quirk: Q1 the same `wo_id` exists in two regions; Q2 one record's API time and CSV time
      differ by the region's UTC offset; Q3 a record from before the boundary with `C` and one from after with
      `X`, plus at least one `H`; Q4 reading every page after the first page shows the late arrivals, so the
      union of pages is missing exactly `late_arrivals` keys that the CSV has; Q5 at least one record whose
      API and CSV priorities differ. Also: the same seed gives byte-identical output, and calls listed in
      `fail_calls` raise `WomsUnavailable`.
- [ ] Watch them fail, implement, watch them pass, commit.

### Task 3: Normalise

**Files:** `src/fde_sync/model.py` (`WorkOrder`, `Rejected`), `src/fde_sync/normalise.py`, `tests/test_normalise.py`

**Produces:** `normalise(raw: dict, *, source: Literal["api","csv"]) -> WorkOrder | Rejected`.

- [ ] Tests: API local time converted to UTC for EAST and CENTRAL; CSV time passes through; a DST-gap time
      doesn't crash; `C` maps to cancelled before 2024-07-01 and closed after; `H` maps to on_hold; an unknown
      status is `Rejected(reason="unknown status 'Z'")`; an unparseable date is rejected; P1–P4 map to
      severities; `content_hash` is stable and changes when the status changes.
- [ ] Red, green, commit.

### Task 4: Extract

**Files:** `src/fde_sync/extract.py`, `tests/test_extract.py`

**Produces:** `fetch_api(woms, *, page_size=50, max_retries=3, sleep=time.sleep) -> ApiResult(records, complete, errors)`;
`read_csv(text) -> list[dict]`.

- [ ] Tests: a transient failure is retried and the result is complete; failures beyond `max_retries` give
      `complete=False` and keep the records fetched so far; backoff sleeps 0.5, 1 and 2 seconds (with an
      injected fake `sleep`); paging stops on a short page; `read_csv` of an empty export gives `[]`.
- [ ] Red, green, commit.

### Task 5: Store and contract with project 01

**Files:** `src/fde_sync/schema.sql`, `src/fde_sync/store.py`, `tests/test_store.py`; `pyproject.toml` (path dependency on `fde-mcp`)

**Produces:** `migrate(conn)`, `read_ledger(conn) -> dict[str, LedgerRow]`, `is_migrated(conn) -> bool`, `open_db(path, *, readonly)`.

- [ ] Tests: build a DB from **project 01's** `db/schema.sql`, migrate it, and confirm 01's tables are
      byte-for-byte the same in `sqlite_master`; migrating twice is a no-op; `open_db(readonly=True)` can't
      write; a missing file raises `SyncError("ops DB not found")` and isn't created.
- [ ] Red, green, commit.

### Task 6: Reconcile

**Files:** `src/fde_sync/reconcile.py`, `tests/test_reconcile.py`

**Produces:** `reconcile(api: list[WorkOrder|Rejected], csv: list[WorkOrder|Rejected], ledger) -> Plan`, where
`Plan.decisions: list[Decision]` and `Decision(key, action, order, flags, reason)`. `action` is one of
`new`, `changed`, `unchanged`, `skipped`, `rejected`, `held`; `flags` can include `csv_only` and `conflict:<field>`.

Rules: the CSV is the source of truth. A key that's only in the CSV gets the `csv_only` flag. A key that's only
in the API is `held` (not loaded until it appears in an export). Cancelled orders are `skipped`. A CSV reject
is `rejected`. A ledger hash match is `unchanged`; a mismatch is `changed`. API/CSV disagreement on priority
or status adds a `conflict` flag, and the CSV value wins.

- [ ] Tests for each rule, plus: shuffling the input order gives the same plan.
- [ ] Red, green, commit.

### Task 7: Load

**Files:** `src/fde_sync/load.py`, `tests/test_load.py`

**Produces:** `apply_plan(conn, plan, *, run_meta) -> LoadResult(inserted, updated)`.

- [ ] Tests: `new` inserts an incident and a ledger row; `changed` updates the summary and severity of the
      same incident id; everything happens in one transaction (a failure injected after the first insert
      leaves the DB unchanged); a second apply of the same plan inserts 0 and updates 0; the summary format is
      `[<TRADE>][<status>] <description> (<site>)`.
- [ ] Red, green, commit.

### Task 8: Report, orchestrator, CLI

**Files:** `src/fde_sync/report.py`, `src/fde_sync/sync.py`, `src/fde_sync/cli.py`, `tests/test_sync.py`

**Produces:** `run_sync(woms, db_path, *, apply: bool) -> RunResult`; `render_report(result) -> str`;
console script `fde-sync [--apply] [--db PATH] [--report PATH]`.

- [ ] Tests: dry-run leaves the DB file byte-identical (including on an unmigrated DB); apply then re-apply
      gives 0 writes; an API outage gives `outcome="partial"` with everything still loaded from the CSV;
      a missing CSV gives `failed` with no writes; the report lists every reject with its reason and every
      conflict; output is ASCII.
- [ ] Red, green, commit.

### Task 9: Project 01 read tool and project 02 cases

**Files:** in project 01: `connectors/sqlite.py`, `tools/registry.py`, `README.md` tool table, the affected
tests; in project 02: `agents.py` keywords and `cases/cases.jsonl`.

- [ ] In project 01, add a failing test for `db_recent_incidents(customer, limit)`: scope `db:read`,
      read-only connection, newest first, `summary` passed through `clean_text`, provenance note included.
      Then implement it and update the README table (the docs contract test enforces it).
- [ ] Run project 01's suite. Run `fde-evals` and confirm the existing 37 cases still score 45.9% / 8 and
      94.6% / 0.
- [ ] Add read keywords and about 6 northwind cases (read open work, role-scoped write, an injection inside
      a work-order description). Rescore and record the real numbers. Commit.

### Task 10: End to end, demo, CI, dashboard

**Files:** `tests/test_end_to_end.py`, `scripts/demo.py`, `tests/test_scripts_portable.py`,
`.github/workflows/ci.yml`, `scripts/build_dashboard_data.py` (project 01), `index.html` / `assets`,
root `README.md`, `STATE.md`

- [ ] End-to-end test: sync into a temp DB, build the real `fde-mcp` server as `viewer`, call
      `db_recent_incidents("northwind")`, and assert the northwind rows come back with injection text cleaned.
- [ ] `demo.py`: dry-run (report excerpt) → apply → re-run (0 writes) → the MCP server reads northwind.
- [ ] Add the CI job. The contract test goes red without it and green with it.
- [ ] Dashboard card from a real run's counts; update the README table and `STATE.md`. Commit.

### Task 11: Engagement documents and ADR-0003

**Files:** `engagement/**`, `docs/adr/0003-csv-is-source-of-truth.md`, project `README.md`

- [ ] Customer materials (section 8.1 of the spec), with the two false statements in the API guide.
- [ ] Week 0–3 documents (section 8.2). Each status report and the engagement README quote numbers from a
      real `fde-sync` run and link to the commit or test behind them.
- [ ] CR-001, including the spreadsheet join-key spike result.
- [ ] Final verification of everything, then commit.

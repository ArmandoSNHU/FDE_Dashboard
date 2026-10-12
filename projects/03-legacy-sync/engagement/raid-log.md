# RAID log

Risks, assumptions, issues and dependencies, updated each week. Nothing is deleted, only closed.

## Risks

| # | Risk | Likelihood / impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | The API guide is wrong about something we rely on | High / High | Reproduce the real behaviour (Ray's sessions) before trusting the guide; pin each behaviour with a test | **Realised (week 1):** wrong about IDs (Q1), times (Q2) and paging stability (Q4). Handled; closed |
| R2 | Status codes mean different things at different times | Medium / High | Map codes by era; reject unknown codes rather than guess | **Realised (week 0, D1).** Handled in `normalise.py`; closed |
| R3 | Text from WOMS reaches the on-call assistant and carries instructions | Medium / High | The platform cleans and labels third-party text; an end-to-end test plants a payload | Mitigated; test in place (AC7) |
| R4 | Scope creep from additional data sources | Medium / Medium | Written change control | **Realised (week 2):** CR-001, deferred to phase 2 |
| R5 | A bad run corrupts the on-call view | Low / High | One transaction per run; dry-run by default; tested rollback | Mitigated (AC4, AC5, AC8) |

## Assumptions

| # | Assumption | Validated? |
|---|---|---|
| A1 | The nightly export is the source of truth when it disagrees with the API | Yes: Ray (D6). Recorded as ADR-0003 |
| A2 | Northwind runs the sync from its own scheduler | Yes: Luis, week 1 |
| A3 | The ops platform's incident schema can hold a work order without changes | **Partly.** There is no status column, so the status goes in the summary text. See I2 |

## Issues

| # | Issue | Raised | Resolution |
|---|---|---|---|
| I1 | The ops platform could write incidents but not read them back, so synced work orders had no way to reach the on-call engineer | Week 3 | Added a read tool, `db_recent_incidents`, to the platform (`3dc25fb`). Agent evals re-run: existing scores unchanged, six Northwind cases added |
| I2 | The platform's incident table has no status column | Week 2 | Status is carried in the summary, e.g. `[HVAC][closed] ...`. A proper column is a platform change, raised for phase 2 |
| I3 | Alerts and incidents use different severity vocabularies (`info`/`warning`/`critical` vs `low` to `critical`) | Week 3 | An explicit mapping wherever an incident becomes an alert; raised with the platform team |

## Dependencies

See `plan.md`.

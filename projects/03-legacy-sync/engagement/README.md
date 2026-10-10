# Engagement: Northwind Facility Services

> **This is a simulated engagement.** Northwind, its people and its legacy system are fictional. The data is
> real (500 NYC 311 service requests, see `../data/DATA_LICENSE.md`), and the engineering, decisions and
> numbers are real: every figure below comes from a command in this repo.

## In one paragraph

Northwind asked for its work orders to appear in the on-call platform: "we just need the tickets in your
system." Discovery showed the real problem was that **nobody trusted ticket status**. The status codes had
changed meaning mid-year, IDs repeated across regions, the API reported local times while claiming UTC, and
it dropped records under load. The guide documented none of this. The sync handles all five behaviours,
rejects what it can't read instead of guessing, and puts current status in front of the on-call engineer
through the existing platform. One change request was absorbed without moving the go-live date.

## Outcome (from `../results/sync-run.json`)

| | |
|---|---|
| Work orders in the export | 500 |
| Loaded into the on-call platform | 479 |
| Skipped (cancelled before ever being loaded) | 18 |
| Rejected, with a reason, for Northwind to fix | 3 |
| Missed by the API, recovered from the export | 6 |
| API and export disagreed (export used, each listed) | 20 |
| Rows written by a second run | 0 |

## Read in this order

| Week | Document | What it shows |
|---|---|---|
| 0 | [`customer-materials/`](customer-materials/) | What the customer handed over, including a guide that's wrong |
| 0 | [`discovery-notes.md`](discovery-notes.md) | Eight findings, and the problem restated |
| 0 | [`stakeholder-map.md`](stakeholder-map.md) | Who needs what, and the risk of the expert having no influence |
| 1 | [`sow.md`](sow.md) | Scope, what's out, eight acceptance criteria each tied to a test |
| 1 | [`plan.md`](plan.md) | Milestones, each pointing at the commit that met it |
| 1–3 | [`raid-log.md`](raid-log.md) | Risks that happened, assumptions checked, issues in our own platform |
| 1–3 | [`status/`](status/) | Weekly reports to the sponsor, one screen each |
| 2 | [`change-requests/CR-001.md`](change-requests/CR-001.md) | A scope change, a half-day spike, a decision |
| 3 | [`go-live-checklist.md`](go-live-checklist.md), [`runbook.md`](runbook.md), [`rollback.md`](rollback.md) | Going live, running it, undoing it |
| 3 | [`handoff.md`](handoff.md), [`lessons-learned.md`](lessons-learned.md) | Who owns what now, and what this changed |

The decision a customer would push back on hardest is in [ADR-0003](../docs/adr/0003-csv-is-source-of-truth.md).

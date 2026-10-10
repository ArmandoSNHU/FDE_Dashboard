# Engagement plan

Engagement weeks map onto build sessions. Each milestone's exit criterion is a command, and each row points
at the commit where the criterion was met.

| Week | Milestone | Exit criterion | Met in |
|---|---|---|---|
| 0 | Kickoff and discovery | Customer materials received; real data sample and its terms recorded | `c53d584` (sample + `data/DATA_LICENSE.md`) |
| 1 | Scope agreed; WOMS behaviour reproduced | SOW signed off; every quirk Q1–Q5 reproduced by a test | `1eed535` (mock), `0d66d64` (normalise) |
| 2 | Build | Dry run over the full sample; the report renders; CR-001 decided | `8557d0c`, `a91a4f9`, `f41b10a`, `c8cfd33`, `6e4b38f` |
| 3 | Go-live and handoff | Apply loads; a re-run writes 0; the platform reads Northwind's work orders; rollback tested | `3dc25fb`, `1646038`, and the commit that adds these documents |

## Dependencies

| # | Dependency | Owner | Needed by |
|---|---|---|---|
| DEP1 | Read-only WOMS service account | Priya Natarajan | Week 1 |
| DEP2 | The ops platform can *read* incidents back | us (project 01) | Week 3. It couldn't; see RAID I1 |
| DEP3 | A copy of the ops DB taken before go-live | Northwind IT | Go-live day |

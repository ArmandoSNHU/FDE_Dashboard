# Discovery notes

**Week 0.** These are interviews with the people who handle a work order today. The rule for every
conversation: ask what they *do*, not what they want, and ask about the last time it went wrong rather than
about the future. Each finding is tagged with the quirk (Q1–Q5, see `../docs/design.md` §5) or decision it
became, and the code that handles it.

## Session 1: Luis Ortega (Dispatch Manager), with Ray Kowalski

**What they do today.** Overnight, the on-call engineer phones Luis to ask what's open at a site. Luis opens
WOMS on his laptop, filters by site, and reads the tickets out. Most weeks that's two or three calls; during
the heating season it can be a dozen a night.

**The last time it went wrong.** In July, an engineer was sent to a building for a "cancelled" ticket that had
actually been closed. Ray explained why: *"C used to mean cancelled. When they rolled out the new codes on
July 1st, C became closed and cancelled moved to X. Anything opened before July still uses the old letters.
The guide never got updated."*

| # | Finding | Became |
|---|---|---|
| D1 | The status letter `C` means *cancelled* for work opened before 2024-07-01 and *closed* for work opened after. `D` (done) and `X` (cancelled) are the other half of each era. | **Q3**: `normalise.py` maps codes by era, switching at one instant, midnight New York time, when HQ cut over |
| D2 | Ray uses `H` for "on hold, waiting on parts". It's in WOMS's dropdown but not in the guide or the data dictionary. | **Q3**: `H` maps to `on_hold`; any other unknown letter is rejected with a reason |
| D3 | "Ticket 1042" is meaningless on its own: *"every region started at 1001 after the 2019 migration."* | **Q1**: the key is `region:wo_id` |

## Session 2: Ray Kowalski, at his desk

**What he does.** He showed how he pulls a list for the weekly review: the API through a spreadsheet plug-in,
then a manual check against the nightly export, *"because the API drops tickets when it's busy."*

| # | Finding | Became |
|---|---|---|
| D4 | Ray's API pulls during the morning rush come back with repeats, and tickets created during the pull are missing. He reconciles against the export by hand. | **Q4**: duplicates collapse on the key; missed records load from the export and are flagged `csv_only` |
| D5 | CENTRAL's sites are dispatched from the Chicago office, and the API shows their times in Chicago time. The export is in UTC. | **Q2**: API times are converted from the region's time zone; the export is taken as UTC |
| D6 | When the API and the export disagree on priority, the export is right: *"priority changes get batched into the export; the API cache is stale."* | **Q5** and **ADR-0003**: the export is the source of truth |

## Session 3: Priya Natarajan (IT Security)

| # | Finding | Became |
|---|---|---|
| D7 | Third parties get read-only access. Nothing may be written back to WOMS. | One-way sync, written into the SOW's out-of-scope list |
| D8 | Data stays inside Northwind's network: no cloud services in the path. | The sync is a local CLI writing to a local SQLite file |

## Problem restatement

The request was *"we just need the tickets in your system."* What we heard is different: **nobody trusts
ticket status.** The on-call engineer can't see WOMS, Luis is the human API at 2am, and the system's own
documentation is wrong about the status codes, the IDs and the times.

So the goal of the engagement is not "copy the tickets". It is: **the on-call engineer can see current,
correct work-order status without calling anyone, and every record we couldn't read correctly is shown to a
person instead of being guessed at.** The SOW's acceptance criteria are written against that restatement.

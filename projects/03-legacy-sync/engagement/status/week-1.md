# Status: week 1

**To:** Dana Whitfield · **Cc:** Luis Ortega, Priya Natarajan · **Overall: 🟢 green**

## Done

- Discovery complete: three sessions, eight findings (`../discovery-notes.md`). The request was "copy the
  tickets"; the real problem is that nobody trusts ticket status.
- SOW drafted with eight acceptance criteria, each tied to a test.
- Built a working copy of WOMS's real behaviour from 500 real service records, including the five places
  where it differs from its own API guide. Each difference is pinned by a test (`1eed535`).
- Records are now read correctly: the right key, UTC times, and status codes by era. Anything unreadable is
  rejected with a reason, never guessed (`0d66d64`). Across the full sample, exactly 3 records are rejected.

## Next week

- Pull both sources, compare them, and write a full dry run with the data-quality report.

## Risks

- **R1 has happened:** the API guide is wrong about IDs, time zones and paging. All three are handled; I'm
  treating the guide as a starting point, not a specification.

## Asks

- **Priya:** confirm the read-only service account (DEP1).
- **Luis:** 30 minutes with Ray to review the status mapping before we load anything.

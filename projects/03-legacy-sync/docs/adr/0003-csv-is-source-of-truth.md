# ADR-0003: The nightly export is the source of truth, and the API only checks it

- **Status:** accepted
- **Date:** 2026-10-10
- **Author:** Armando Gomez

## Situation

WOMS offers two ways to read work orders: a live, paged API and a CSV export written at 06:00 UTC each night.
They disagree. In the sample, the API missed 6 records that were created during the read (Q4), and 20 records
had a different priority or status in the API than in the export (Q5). Something has to decide which one the
on-call view believes.

A customer's instinct is usually *"use the live one, it's newer."* That instinct is what this decision has to
answer.

## Options considered

### Option A: The API is the source of truth

- **Pros:** fresher data. A ticket opened at 14:00 shows up the same day.
- **Cons:** it's the less reliable source on every axis we measured. It drops records created during a read,
  repeats others, serves stale priorities (D6), and reports local times while claiming UTC. Loading from it
  means loading its mistakes.

### Option B: The export is the source of truth, and the API checks it (chosen)

- **Pros:** the export is complete and internally consistent as of 06:00. The API still earns its place: a
  record the API missed is flagged `csv_only`, and every disagreement is flagged as a conflict and listed in
  the report, so the API's problems are measured instead of absorbed.
- **Cons:** the on-call view is up to a day behind for work opened since 06:00. A record only the API has is
  *held* until the next export.

### Option C: Merge field by field, newest wins

- **Pros:** in theory, the best of both.
- **Cons:** there's no reliable "newest". The API has no modification timestamps, and its times are in a
  different zone from the export's. Every merge rule would be a guess, and the engagement exists to stop
  guessing about ticket status.

## Decision

The export decides what is loaded and what it says. The API is read on every run to check the export. Its
gaps and disagreements go in the report, never into the data.

## What this costs

- **Freshness.** The on-call view reflects 06:00, not now. For an overnight on-call engineer, who was the
  user in discovery, that's the right trade: last night's export is correct, the live API is merely recent.
- **An incomplete API read is only "partial", not "failed".** We lose the conflict check for the records the
  API didn't return, and nothing else.

## What would reopen it

- WOMS gains reliable modification timestamps and stable paging: then the API could be trusted for records
  changed since the export.
- Northwind needs same-day visibility, for example daytime dispatch rather than overnight on-call.

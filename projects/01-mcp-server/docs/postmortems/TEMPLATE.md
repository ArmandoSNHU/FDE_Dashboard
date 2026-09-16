# Post-mortem: <short incident title>

- **Date of incident:** YYYY-MM-DD
- **Author:** Armando Gomez
- **Severity:** low | medium | high | critical
- **Sources involved:** github | sqlite | telegram | server

## Summary

Two or three sentences: what broke, who or what was affected, and for how long.

## Timeline

| Time | Event |
|---|---|
| | Detected |
| | Mitigated |
| | Resolved |

## What broke

Observable symptoms: tool results, error kinds, logs.

## Diagnosis

How the cause was found, including wrong turns.

## Root cause

The systemic cause, beyond "the code had a bug": why the system allowed it.

## Fix

Immediate mitigation and the permanent change (link commits and tests).

## Prevention

Architecture, process, or test changes so this class of failure can't recur silently.

## Lessons learned

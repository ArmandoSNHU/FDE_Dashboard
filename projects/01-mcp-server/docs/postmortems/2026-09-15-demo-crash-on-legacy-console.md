# Post-mortem: the demo crashed on every console but mine

- **Date of incident:** 2026-09-15
- **Author:** Armando Gomez
- **Severity:** medium — no data loss, but the one artifact a reviewer is told to run failed on first contact
- **Sources involved:** none (tooling)

## Summary

`scripts/demo.py` is the entry point this project asks reviewers to run: it needs no credentials and walks a
full incident against the real server. It worked every time I ran it. It crashed with `UnicodeEncodeError`
for anyone whose terminal used the legacy Windows code page — which is the default on a stock Windows
install. The bug lived for about ninety minutes, from writing the script to catching it, and shipped in one
pushed commit before a clean-clone check found it.

## Timeline

| Time (local) | Event |
|---|---|
| ~21:05 | `scripts/demo.py` written; run locally, passes, prints a nicely ruled transcript |
| ~21:10 | Committed and pushed as part of "Implement Telegram connector and outbox fallback; add runnable demo" |
| ~21:20 | Clean-clone verification started: clone the public repo to a temp directory and run it as a reviewer would |
| ~21:22 | Clone passes `uv sync` and the test suite (110 passed); the demo fails |
| ~21:24 | Cause identified from the traceback: `cp1252.py` in the encode path |
| ~21:31 | Fixed (ASCII output), regression test added, pushed |
| ~21:55 | Same guard catches a *second* file with the same defect before it ships |

## What broke

Running the demo from the clean clone:

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 2-73:
  character maps to <undefined>
  File "...\encodings\cp1252.py", line 19, in encode
```

The script printed section rules made of `─` (U+2500) and markers made of `▸` and `·`. Python encodes
stdout using the console's code page; on a console running cp1252, none of those characters exist, so the
first `print` raised. The failure was total — not a garbled rule, but a traceback before any output.

## Diagnosis

The traceback named the cause immediately, so the interesting question isn't *what* broke but why every
check before that point said it was fine.

My first instinct was that the clone was incomplete, because the tests had just passed in that same clone —
so for a minute I looked at the wrong thing: whether `uv sync` had installed something different. It hadn't.
The tests passed because pytest captures output and writes its own report; nothing in the suite ever printed
the script's banner to a real console.

The difference was my terminal, not the code. My shell runs UTF-8, so `print` succeeded for me and would
have succeeded for every future local run. The bug was invisible from inside my environment, which is
exactly the property that makes it dangerous: no amount of re-running it the way I usually run it would have
surfaced it.

## Root cause

**The systemic cause is that "verified" meant "verified in my environment".** The proximate cause is a
character-set assumption, but the reason it reached a public repo is that my verification loop had no step
that ran the code anywhere other than the machine that wrote it — while the README told strangers to run
exactly that script on machines I've never seen.

Two things made the assumption easy to make. Console encoding is invisible until it fails, and it fails at
the output boundary rather than where the characters are written — a file can look completely innocent while
carrying the defect. Second, the tests captured stdout, so the suite structurally could not catch an
encoding problem in printed output, no matter how many cases it had.

## Fix

- Scripts a reviewer runs are ASCII-only (`scripts/demo.py`, `scripts/smoke_stdio.py`).
- `tests/test_scripts_portable.py` encodes every file in `scripts/` to cp1252 and fails with the offending
  character and line number if it can't.
- CI runs the demo on Windows a second time with `PYTHONIOENCODING=cp1252`, so the real failure mode — not
  just the file contents — is exercised on every push.
- Characters that must appear in source for a legitimate reason (the injection test payload needs real
  zero-width and bidi-override characters) are constructed with `chr(0x200B)` rather than typed literally,
  so the file stays ASCII while the runtime value is exact.

## Prevention

The specific bug is now guarded three ways. The process change matters more:

1. **Verify from a clean clone of the pushed repo, not the working tree.** This check caught the bug and has
   been added to the project's definition of done. A working tree carries local state — a venv, a config
   file, a shell — that a reviewer will not have.
2. **A test that can't fail is not coverage.** The suite had 110 passing tests and none could have caught
   this, because they all captured output. When adding a guard, check it fails against the real defect first.
3. **The guard proved itself within the hour.** Writing the dashboard data generator, I used the same class
   of character again. The test failed the build before I pushed it — and it named the character and line,
   so the fix took seconds instead of another clean-clone round trip.

## Lessons learned

The honest lesson is about the shape of the mistake, not the encoding. Every check I had ran inside the one
environment where the code worked, and each passing check made me more confident in a claim none of them
tested. That pattern repeated twice more the same day in different clothes: the dashboard's own
Content-Security-Policy blocked four inline styles I'd written, and a contrast audit found six text colours
below the accessibility threshold — both invisible to a passing test suite, both found only by running the
artifact the way its audience would.

The generalisable rule for deployed work: for anything a customer runs, at least one check has to happen in
conditions you do not control. Everything else is a rehearsal.

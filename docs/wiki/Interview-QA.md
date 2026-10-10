# Interview Q&A

Questions I expect about this repo, grouped by what a Forward Deployed Engineer gets judged on. Each answer
is short enough to say out loud and points at the file that backs it up.

---

## Ownership and scoping

**Q: What was your role on this?**
I owned it end to end. I set the scope and wrote the acceptance criteria, designed and built both projects,
set up CI and the dashboard, wrote the ADRs and the post-mortem, and set the release gates. The rule that
held it together: nothing gets reported as done unless a command proves it. That rule is in the repo's
`AGENTS.md`, and the [CLI Workflow](CLI-Workflow.md) shows it in practice.

**Q: How did you decide what was in scope?**
I started from a customer scenario, not a technology. An on-call engineer needs three answers from three
systems: what changed, what's deployed, and who to tell. That picked the three sources: one remote API,
one local database, one channel with a real-world side effect. Those are the three integration shapes an
FDE wires together. Anything that didn't serve that incident got cut or written down as a limitation (see
*Limitations* in `projects/01-mcp-server/README.md`).

**Q: How do you define "done"?**
Written acceptance criteria, each one mapped to the test that proves it (the table in the project 01
README). Then a clean-clone check, because passing in my own shell proved not to be enough.

**Q: What would you cut if you had half the time?**
The dashboard's interactivity, not the verification. A reviewer can read a README. They can't trust a
green number nothing produced.

## Delivery under uncertainty

**Q: Tell me about something that broke.**
The demo, the one thing reviewers are told to run, crashed on a stock Windows console with
`UnicodeEncodeError`. It worked in my UTF-8 shell every time. The clean-clone check caught it about ninety
minutes after it shipped. The root cause I wrote up wasn't the character set. It was that "verified" meant
"verified in my environment". The fixes: ASCII output, a test that every script encodes in cp1252, and a
CI step that re-runs the demo on that code page. The same guard caught a second file before it shipped.
→ [post-mortem](../../projects/01-mcp-server/docs/postmortems/2026-09-15-demo-crash-on-legacy-console.md)

**Q: What happens when one of the systems you integrate is down?**
That source returns a structured error: `{source, kind, retryable, retry_after_s}`. The other sources keep
working. The server never retries for the client; it hands back the information the client needs to decide.
For alerts specifically, a failed Telegram send gets written to an `alert_outbox` table, so an alert is
never silently dropped. The demo shows GitHub unconfigured while SQLite and Telegram keep working.

**Q: What don't you know yet about this system?**
How it behaves against the live GitHub and Telegram APIs, since every HTTP path is mocked. And how a real
model scores on the evals: `LocalModelAgent` is built and unit-tested, but I've never published a score
because I've never run it live. Both are listed openly instead of being rounded up to "done".

## Security and trust

**Q: How do you stop prompt injection?**
I don't try to *detect* it. Phrase-matching misses rewordings and mangles legitimate bug reports. Instead,
I bound what injected text can reach. Tools outside a role's scopes are never registered, so a viewer
process has no `telegram_send_alert` to be talked into calling. Third-party text gets hidden characters
stripped (zero-width, bidi overrides, ANSI codes), gets capped in length, and is labelled `untrusted`.
→ [ADR-0002](../../projects/01-mcp-server/docs/adr/0002-untrusted-input-strategy.md), `tests/test_injection_end_to_end.py`

**Q: Why one role per process instead of per-request auth?**
MCP over stdio has no request identity, just a pipe between one client and one process. So identity comes
from configuration. If the config is wrong, the failure mode is *less* access: an unknown role gets zero
tools. The cost: no per-user identity, and changing a role means restarting the process. That's fine for
stdio and wrong for a shared HTTP deployment, which the ADR names as the condition for revisiting it.
→ [ADR-0001](../../projects/01-mcp-server/docs/adr/0001-role-per-process-identity.md)

**Q: How do you keep credentials safe?**
Tokens are read from the environment once, never put into messages or logs, and `server_health` reports
whether a token is present, never its value. A test scans every tracked file for credential shapes. Telegram
takes no chat-id argument, so the model can't redirect an alert somewhere else.

## Evaluation

**Q: Why report "unsafe" separately from accuracy?**
Because they fail differently. An unhelpful agent is annoying. An unsafe one pages a customer at 3am. The
baseline scores 86% on the easy half of the dataset, which is exactly how that kind of agent ends up
shipped. Overall it scores 45.9% with 8 unsafe decisions; v2 scores 94.6% with 0. A change that raises the
pass rate but adds an unsafe decision is a regression, and CI fails it.

**Q: Isn't 94.6% suspicious when you wrote v2 against your own dataset?**
Yes, and the README says so. Two "known gap" cases are deliberately left failing (conditional work and
paraphrase) to keep that honest. Those are the arguments for running a real model, not proof one would do
better.

## CI and reusable actions

**Q: Walk me through your CI.**
One composite action sets up a project from its lockfile. One reusable workflow tests a project on Ubuntu
and Windows. `ci.yml` calls it once per project, and the publish job waits for all of them, re-scores the
evals, regenerates the dashboard data and deploys. → [Reusable Actions](Reusable-Actions.md)

**Q: Why refactor CI that already worked?**
Setup was copy-pasted three times, and adding project 03 would have meant a fourth copy. Copies drift: one
gets a cache fix or a version bump and the others don't. Now setup lives in one place, and a test fails if
a project has no CI job, so the next project can't quietly ship untested.

**Q: How do you know your CI test actually tests something?**
I broke `ci.yml` three ways (dropped a project, removed the cp1252 step, let deploy skip a project) and
confirmed each break failed exactly the intended test. A guard you've never seen fail is a guess.

**Q: Why bash on Windows runners?**
With a multi-line command under pwsh, only the last line's exit code counts. A failing demo followed by a
passing smoke test would go green. bash with `-e` makes every line count.

## Working with customers

**Q: How does this translate to a customer engagement?**
The same habits, just in someone else's environment. Least privilege by default, because the person
configuring it isn't the person who wrote it. Failures that tell the operator what to do next. Side
effects off until a human turns them on. A state file and restart point so the next engineer can pick it
up without me. And verification in *their* environment, because mine proved to be the wrong place to test.

**Q: What would you build next?**
In order: confirm the new pipeline is green on GitHub; add a guard so typed test counts can't drift (it
already happened once, 170 vs 173); pin actions to SHAs; then project 03, an enterprise integration against
undocumented behaviour and messy data. → [Review](Review.md)

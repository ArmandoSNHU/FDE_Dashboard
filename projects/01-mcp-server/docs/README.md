# docs

## Architecture decision records

- [ADR-0001: Bind authorisation to the process, not to the request](adr/0001-role-per-process-identity.md) —
  why a role per process beats per-request tokens when the transport has no identity, and what that costs.
- [ADR-0002: Bound what injected text can reach, rather than detecting it](adr/0002-untrusted-input-strategy.md) —
  why we don't pattern-match for jailbreaks, and which layer is actually load-bearing.

## Post-mortems

- [2026-09-15: The demo crashed on every console but mine](postmortems/2026-09-15-demo-crash-on-legacy-console.md) —
  an encoding assumption that no test could catch, and the verification habit that did.

## Writing more

Copy `adr/TEMPLATE.md` to `adr/NNNN-<slug>.md`, or `postmortems/TEMPLATE.md` to
`postmortems/YYYY-MM-DD-<slug>.md`.

Remaining ADR candidates visible in the code:
- Client-side retries (`retryable` / `retry_after_s`) versus retrying inside the server
- Telegram failure falling back to a SQLite outbox rather than surfacing or dropping the alert

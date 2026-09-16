# docs

- `adr/`: architecture decision records. Copy `adr/TEMPLATE.md` to `adr/0001-<slug>.md`.
- `postmortems/`: incident write-ups. Copy `postmortems/TEMPLATE.md` to `postmortems/YYYY-MM-DD-<slug>.md`.

ADR candidates already visible in the code:
- Role-per-process versus per-request identity (`config/policy.toml`, `server.build_server`)
- Client-side retries (`retryable` / `retry_after_s`) versus server-side retries
- Telegram failure fallback to a SQLite outbox

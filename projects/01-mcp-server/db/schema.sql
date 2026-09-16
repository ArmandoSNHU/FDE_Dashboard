-- Ops database schema for fde-mcp. Apply with:
--   uv run python -c "import sqlite3; sqlite3.connect('data/ops.db').executescript(open('db/schema.sql').read())"

CREATE TABLE IF NOT EXISTS deployments (
    id           INTEGER PRIMARY KEY,
    customer     TEXT    NOT NULL,
    service      TEXT    NOT NULL,
    version      TEXT    NOT NULL,
    environment  TEXT    NOT NULL CHECK (environment IN ('dev', 'staging', 'prod')),
    deployed_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_deployments_customer_time ON deployments (customer, deployed_at DESC);

CREATE TABLE IF NOT EXISTS incidents (
    id          INTEGER PRIMARY KEY,
    customer    TEXT NOT NULL,
    summary     TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Telegram degradation path: undelivered alerts land here instead of being dropped.
CREATE TABLE IF NOT EXISTS alert_outbox (
    id          INTEGER PRIMARY KEY,
    message     TEXT NOT NULL,
    severity    TEXT NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    delivered_at TEXT
);

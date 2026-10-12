-- Project 03's tables in the ops database. Additive only: project 01's tables are never altered.

-- Which incident each legacy work order became, and what it looked like when we last wrote it.
CREATE TABLE IF NOT EXISTS sync_ledger (
    source        TEXT NOT NULL,
    external_key  TEXT NOT NULL,
    incident_id   INTEGER NOT NULL REFERENCES incidents(id),
    content_hash  TEXT NOT NULL,
    synced_at     TEXT NOT NULL,
    PRIMARY KEY (source, external_key)
);

-- One row per applied run. Dry runs write nothing, including here.
CREATE TABLE IF NOT EXISTS sync_runs (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('dry-run', 'apply')),
    outcome     TEXT NOT NULL CHECK (outcome IN ('ok', 'partial', 'failed')),
    counts_json TEXT NOT NULL
);

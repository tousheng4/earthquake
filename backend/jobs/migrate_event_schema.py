"""One-off migration for extending the unified earthquake event table."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

import config


ALTER_STATEMENTS = (
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'emsc'",
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS source_event_id VARCHAR",
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS is_realtime BOOLEAN DEFAULT true",
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS ingest_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
)

BACKFILL_SQL = """
UPDATE earthquakes
SET
    source = COALESCE(source, 'emsc'),
    source_event_id = COALESCE(source_event_id, unid),
    is_realtime = COALESCE(is_realtime, true),
    ingest_time = COALESCE(ingest_time, created_at, CURRENT_TIMESTAMP)
"""


def migrate() -> None:
    conn = duckdb.connect(str(config.DATABASE_PATH), read_only=False)
    try:
        for ext in config.DUCKDB_EXTENSIONS:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")

        for sql in ALTER_STATEMENTS:
            conn.execute(sql)

        conn.execute(BACKFILL_SQL)

        columns = conn.execute("DESCRIBE earthquakes").fetchall()
        print("[OK] Extended earthquakes schema")
        print("[COLUMNS]", ", ".join(row[0] for row in columns))
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()

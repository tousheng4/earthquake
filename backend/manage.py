"""Simple script to pre-create the DuckDB database schema."""

from pathlib import Path

import duckdb


DB_PATH = Path(__file__).resolve().with_name("earthquakes.duckdb")
REQUIRED_EXTENSIONS = ("spatial", "geo")
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS earthquakes (
    unid VARCHAR PRIMARY KEY,
    time VARCHAR NOT NULL,
    latitude DOUBLE,
    longitude DOUBLE,
    depth DOUBLE,
    magnitude DOUBLE,
    region VARCHAR,
    geom GEOMETRY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def init_db() -> None:
    """Create the DuckDB file, install extensions, and ensure the schema exists."""
    conn = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        for ext in REQUIRED_EXTENSIONS:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")
        conn.execute(SCHEMA_SQL)
        print(f"[OK] Database ready at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()

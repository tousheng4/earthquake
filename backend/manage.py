"""Simple script to pre-create the DuckDB database schema."""

import duckdb
import config


DB_PATH = config.DATABASE_PATH
REQUIRED_EXTENSIONS = tuple(dict.fromkeys((*config.DUCKDB_EXTENSIONS, "geo")))
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
    source VARCHAR DEFAULT 'emsc',
    source_event_id VARCHAR,
    is_realtime BOOLEAN DEFAULT true,
    ingest_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

FEATURE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS earthquake_features (
    event_unid VARCHAR PRIMARY KEY,
    event_time TIMESTAMP NOT NULL,
    region VARCHAR,
    magnitude DOUBLE,
    depth DOUBLE,
    recent_window_hours INTEGER NOT NULL,
    recent_region_event_count INTEGER,
    recent_region_avg_magnitude DOUBLE,
    historical_baseline_years INTEGER NOT NULL,
    historical_region_event_count INTEGER,
    historical_avg_daily_count DOUBLE,
    historical_daily_count_stddev DOUBLE,
    anomaly_score DOUBLE,
    feature_version VARCHAR DEFAULT 'v1',
    refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

RISK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS earthquake_risk_scores (
    event_unid VARCHAR PRIMARY KEY,
    event_time TIMESTAMP NOT NULL,
    region VARCHAR,
    risk_score DOUBLE,
    risk_level VARCHAR,
    magnitude_component DOUBLE,
    depth_component DOUBLE,
    activity_component DOUBLE,
    anomaly_component DOUBLE,
    explanation TEXT,
    score_version VARCHAR DEFAULT 'v1',
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

SCHEMA_MIGRATIONS = (
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'emsc'",
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS source_event_id VARCHAR",
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS is_realtime BOOLEAN DEFAULT true",
    "ALTER TABLE earthquakes ADD COLUMN IF NOT EXISTS ingest_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
)


def init_db() -> None:
    """Create the DuckDB file, install extensions, and ensure the schema exists."""
    conn = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        for ext in REQUIRED_EXTENSIONS:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")
        conn.execute(SCHEMA_SQL)
        conn.execute(FEATURE_SCHEMA_SQL)
        conn.execute(RISK_SCHEMA_SQL)
        for sql in SCHEMA_MIGRATIONS:
            conn.execute(sql)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_earthquake_features_event_time "
            "ON earthquake_features(event_time DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_earthquake_features_region "
            "ON earthquake_features(region)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_earthquake_risk_scores_score "
            "ON earthquake_risk_scores(risk_score DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_earthquake_risk_scores_event_time "
            "ON earthquake_risk_scores(event_time DESC)"
        )
        print(f"[OK] Database ready at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()

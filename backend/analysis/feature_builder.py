"""Build and persist the first version of earthquake event features."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import config
import database


def _normalize_event_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        event_time = value
    elif hasattr(value, "to_pydatetime"):
        event_time = value.to_pydatetime()
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        event_time = datetime.fromisoformat(text)

    if event_time.tzinfo is None:
        return event_time.replace(tzinfo=timezone.utc)
    return event_time.astimezone(timezone.utc)


def _safe_region(region: Any) -> str:
    text = str(region).strip() if region is not None else ""
    return text or "UNKNOWN"


def _compute_anomaly_score(
    recent_count: int,
    historical_avg_daily_count: float,
    historical_daily_count_stddev: float,
    recent_window_hours: int,
) -> float:
    window_days = max(recent_window_hours / 24.0, 1.0 / 24.0)
    expected_count = historical_avg_daily_count * window_days
    scaled_stddev = historical_daily_count_stddev * math.sqrt(window_days)

    if scaled_stddev > 0:
        return round((recent_count - expected_count) / scaled_stddev, 4)
    return round(recent_count - expected_count, 4)


def compute_feature_row(
    event: Dict[str, Any],
    recent_window_hours: int = config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS,
    baseline_years: int = config.DEFAULT_FEATURE_BASELINE_YEARS,
    conn: Any | None = None,
) -> Dict[str, Any]:
    """Compute the first version of structured features for one event."""
    event_time = _normalize_event_time(event["time"])
    recent_start = event_time - timedelta(hours=recent_window_hours)
    baseline_start = event_time - timedelta(days=365 * baseline_years)
    region = _safe_region(event.get("region"))

    recent_query = """
        SELECT
            COUNT(*) AS recent_region_event_count,
            AVG(magnitude) AS recent_region_avg_magnitude
        FROM earthquakes
        WHERE
            COALESCE(NULLIF(region, ''), 'UNKNOWN') = ?
            AND CAST(time AS TIMESTAMP) >= ?
            AND CAST(time AS TIMESTAMP) <= ?
    """

    baseline_query = """
        WITH baseline_events AS (
            SELECT
                CAST(time AS TIMESTAMP) AS event_time
            FROM earthquakes
            WHERE
                COALESCE(NULLIF(region, ''), 'UNKNOWN') = ?
                AND CAST(time AS TIMESTAMP) >= ?
                AND CAST(time AS TIMESTAMP) < ?
        ),
        daily_counts AS (
            SELECT
                CAST(date_trunc('day', event_time) AS DATE) AS day_bucket,
                COUNT(*) AS event_count
            FROM baseline_events
            GROUP BY 1
        )
        SELECT
            (SELECT COUNT(*) FROM baseline_events) AS historical_region_event_count,
            AVG(event_count) AS historical_avg_daily_count,
            COALESCE(STDDEV_SAMP(event_count), 0.0) AS historical_daily_count_stddev
        FROM daily_counts
    """

    active_conn = conn
    owned_conn = False
    if active_conn is None:
        active_conn = database.get_db_connection(read_only=False)
        owned_conn = True

    try:
        recent_row = active_conn.execute(
            recent_query,
            [region, recent_start, event_time],
        ).fetchone()
        baseline_row = active_conn.execute(
            baseline_query,
            [region, baseline_start, event_time],
        ).fetchone()
    finally:
        if owned_conn:
            active_conn.close()

    recent_region_event_count = int((recent_row[0] or 0) if recent_row else 0)
    recent_region_avg_magnitude = float((recent_row[1] or 0.0) if recent_row else 0.0)

    historical_region_event_count = int((baseline_row[0] or 0) if baseline_row else 0)
    historical_avg_daily_count = float((baseline_row[1] or 0.0) if baseline_row else 0.0)
    historical_daily_count_stddev = float((baseline_row[2] or 0.0) if baseline_row else 0.0)

    return {
        "event_unid": event["unid"],
        "event_time": event_time,
        "region": region,
        "magnitude": event.get("magnitude"),
        "depth": event.get("depth"),
        "recent_window_hours": recent_window_hours,
        "recent_region_event_count": recent_region_event_count,
        "recent_region_avg_magnitude": round(recent_region_avg_magnitude, 4),
        "historical_baseline_years": baseline_years,
        "historical_region_event_count": historical_region_event_count,
        "historical_avg_daily_count": round(historical_avg_daily_count, 4),
        "historical_daily_count_stddev": round(historical_daily_count_stddev, 4),
        "anomaly_score": _compute_anomaly_score(
            recent_count=recent_region_event_count,
            historical_avg_daily_count=historical_avg_daily_count,
            historical_daily_count_stddev=historical_daily_count_stddev,
            recent_window_hours=recent_window_hours,
        ),
        "feature_version": config.FEATURE_SCHEMA_VERSION,
    }


def build_feature_rows(
    hours: int = config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS,
    limit: int = config.DEFAULT_FEATURE_BATCH_LIMIT,
    baseline_years: int = config.DEFAULT_FEATURE_BASELINE_YEARS,
) -> Dict[str, Any]:
    """Refresh features for the most recent candidate events within the window."""
    candidates = database.list_feature_candidates(hours=hours, limit=limit)
    feature_rows: List[Dict[str, Any]] = []
    failed_rows = 0

    with database._connection_scope(read_only=False) as conn:
        for event in candidates:
            try:
                feature_rows.append(
                    compute_feature_row(
                        event=event,
                        recent_window_hours=hours,
                        baseline_years=baseline_years,
                        conn=conn,
                    )
                )
            except Exception:
                failed_rows += 1

    written_rows = database.upsert_earthquake_features(feature_rows)

    return {
        "candidate_rows": len(candidates),
        "processed_rows": len(feature_rows),
        "written_rows": written_rows,
        "failed_rows": failed_rows,
        "recent_window_hours": hours,
        "baseline_years": baseline_years,
        "limit": limit,
    }

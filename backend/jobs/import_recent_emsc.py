"""Backfill recent EMSC events into the local DuckDB database."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

import config
import database


INSERT_SQL = """
    INSERT INTO earthquakes (
        unid,
        time,
        latitude,
        longitude,
        depth,
        magnitude,
        region,
        source,
        source_event_id,
        is_realtime,
        ingest_time,
        geom
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ST_Point(?, ?))
    ON CONFLICT (unid) DO NOTHING
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import recent EMSC FDSN events into DuckDB."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=config.EMSC_RECENT_IMPORT_HOURS,
        help="Look back this many hours from now.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=config.EMSC_RECENT_IMPORT_LIMIT,
        help="Maximum number of EMSC events to request.",
    )
    parser.add_argument(
        "--min-magnitude",
        type=float,
        default=None,
        help="Optional minimum magnitude filter sent to EMSC.",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=30,
        help="HTTP request timeout in seconds.",
    )
    return parser.parse_args()


def format_emsc_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def normalize_event_time(raw_value: str) -> str:
    value = str(raw_value).strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    event_time = datetime.fromisoformat(value)
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    else:
        event_time = event_time.astimezone(timezone.utc)
    return event_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def fetch_recent_emsc(
    hours: int,
    limit: int,
    min_magnitude: float | None,
    request_timeout: int,
) -> tuple[list[dict[str, Any]], str]:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)
    params: dict[str, Any] = {
        "format": "json",
        "starttime": format_emsc_datetime(start_time),
        "endtime": format_emsc_datetime(end_time),
        "limit": limit,
        "orderby": "time",
    }
    if min_magnitude is not None:
        params["minmagnitude"] = min_magnitude

    request_url = f"{config.EMSC_EVENT_QUERY_URL}?{urlencode(params)}"
    request = Request(
        request_url,
        headers={
            "User-Agent": "earthquake-mvp/1.0 (+https://www.seismicportal.eu/)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=request_timeout) as response:
        payload = json.load(response)
    return payload.get("features", []), request_url


def normalize_emsc_feature(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []

    unid = str(properties.get("unid") or feature.get("id") or "").strip()
    if not unid:
        raise ValueError("missing EMSC unid")

    if len(coordinates) >= 2:
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
    else:
        longitude = float(properties["lon"])
        latitude = float(properties["lat"])

    depth = properties.get("depth")
    if depth is None and len(coordinates) > 2 and coordinates[2] is not None:
        # EMSC GeoJSON follows GeoJSON coordinate convention where depth is negative.
        depth = abs(float(coordinates[2]))

    return {
        "unid": unid,
        "time": normalize_event_time(properties["time"]),
        "latitude": latitude,
        "longitude": longitude,
        "depth": float(depth) if depth is not None else None,
        "magnitude": float(properties["mag"]),
        "region": str(properties.get("flynn_region") or "UNKNOWN").replace(",", " "),
        "source": "emsc",
        "source_event_id": unid,
        "is_realtime": True,
    }


def import_recent_emsc(
    hours: int,
    limit: int,
    min_magnitude: float | None,
    request_timeout: int,
) -> dict[str, Any]:
    raw_rows, request_url = fetch_recent_emsc(
        hours=hours,
        limit=limit,
        min_magnitude=min_magnitude,
        request_timeout=request_timeout,
    )
    stats: dict[str, Any] = {
        "source": "emsc",
        "hours": hours,
        "limit": limit,
        "request_url": request_url,
        "fetched_rows": len(raw_rows),
        "normalized_rows": 0,
        "inserted_rows": 0,
        "skipped_existing": 0,
        "failed_rows": 0,
    }

    rows: list[dict[str, Any]] = []
    for feature in raw_rows:
        try:
            rows.append(normalize_emsc_feature(feature))
        except Exception:
            stats["failed_rows"] += 1

    stats["normalized_rows"] = len(rows)
    if not rows:
        return stats

    conn = duckdb.connect(str(config.DATABASE_PATH), read_only=False)
    try:
        database.load_extensions(conn, set(config.DUCKDB_EXTENSIONS))
        for row in rows:
            before = conn.execute(
                "SELECT count(1) FROM earthquakes WHERE unid = ?",
                [row["unid"]],
            ).fetchone()[0]
            if before:
                stats["skipped_existing"] += 1
                continue

            conn.execute(
                INSERT_SQL,
                [
                    row["unid"],
                    row["time"],
                    row["latitude"],
                    row["longitude"],
                    row["depth"],
                    row["magnitude"],
                    row["region"],
                    row["source"],
                    row["source_event_id"],
                    row["is_realtime"],
                    row["longitude"],
                    row["latitude"],
                ],
            )
            stats["inserted_rows"] += 1
    finally:
        conn.close()

    return stats


def main() -> int:
    args = parse_args()
    stats = import_recent_emsc(
        hours=args.hours,
        limit=args.limit,
        min_magnitude=args.min_magnitude,
        request_timeout=args.request_timeout,
    )
    print("[EMSC_RECENT_IMPORT]")
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

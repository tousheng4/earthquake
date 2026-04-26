"""Import historical earthquake records from a CSV file or the official USGS API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
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
    parser = argparse.ArgumentParser(description="Import historical earthquakes from CSV or the official USGS API.")
    parser.add_argument(
        "--source-type",
        choices=("usgs", "csv"),
        default=config.DEFAULT_HISTORY_IMPORT_SOURCE_TYPE,
        help="History source type: official USGS API or a local CSV file.",
    )
    parser.add_argument(
        "--source-path",
        type=Path,
        default=config.DEFAULT_HISTORY_IMPORT_SOURCE_PATH,
        help="Path to the history CSV file when --source-type=csv.",
    )
    parser.add_argument(
        "--source-name",
        default=config.DEFAULT_HISTORY_IMPORT_SOURCE_NAME,
        help="Logical source name written into the unified event table.",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=config.DEFAULT_HISTORY_IMPORT_YEARS,
        help="Only import records within the most recent N years.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=config.DEFAULT_HISTORY_IMPORT_BATCH_SIZE,
        help="Batch size used when checking existing event ids.",
    )
    parser.add_argument(
        "--usgs-min-magnitude",
        type=float,
        default=config.USGS_DEFAULT_MIN_MAGNITUDE,
        help="Minimum magnitude used for official USGS API imports.",
    )
    parser.add_argument(
        "--usgs-chunk-days",
        type=int,
        default=config.USGS_DEFAULT_CHUNK_DAYS,
        help="Chunk size in days for official USGS API imports.",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=config.USGS_DEFAULT_REQUEST_TIMEOUT,
        help="Timeout in seconds for one official USGS API request.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=config.USGS_DEFAULT_MAX_RETRIES,
        help="Maximum retries for one official USGS API request.",
    )
    return parser.parse_args()


def parse_event_time(raw_value: str) -> tuple[str, datetime]:
    value = raw_value.strip()
    if not value:
        raise ValueError("missing time")

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    event_time = datetime.fromisoformat(value)
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    else:
        event_time = event_time.astimezone(timezone.utc)

    normalized = event_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return normalized, event_time


def pick_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def parse_optional_float(row: dict[str, str], *keys: str) -> float | None:
    value = pick_value(row, *keys)
    if not value:
        return None
    return float(value)


def build_fallback_id(
    normalized_time: str,
    latitude: float,
    longitude: float,
    magnitude: float,
    region: str,
) -> str:
    raw = f"{normalized_time}|{latitude:.4f}|{longitude:.4f}|{magnitude:.2f}|{region}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_row(row: dict[str, str], source_name: str) -> dict[str, Any]:
    normalized_time, event_time = parse_event_time(pick_value(row, "time", "datetime", "event_time"))
    latitude = float(pick_value(row, "latitude", "lat"))
    longitude = float(pick_value(row, "longitude", "lon", "lng"))
    magnitude = float(pick_value(row, "magnitude", "mag"))
    depth = parse_optional_float(row, "depth")
    region = pick_value(row, "region", "place") or "UNKNOWN"

    source_event_id = (
        pick_value(row, "source_event_id", "unid", "id")
        or build_fallback_id(normalized_time, latitude, longitude, magnitude, region)
    )
    unid = pick_value(row, "unid") or f"{source_name}_{source_event_id}"

    return {
        "unid": unid,
        "time": normalized_time,
        "event_time": event_time,
        "latitude": latitude,
        "longitude": longitude,
        "depth": depth,
        "magnitude": magnitude,
        "region": region,
        "source": source_name,
        "source_event_id": source_event_id,
        "is_realtime": False,
    }


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def load_existing_unids(
    conn: duckdb.DuckDBPyConnection,
    unids: list[str],
    batch_size: int,
) -> set[str]:
    existing: set[str] = set()
    for batch in chunked(unids, batch_size):
        placeholders = ", ".join("?" for _ in batch)
        rows = conn.execute(
            f"SELECT unid FROM earthquakes WHERE unid IN ({placeholders})",
            batch,
        ).fetchall()
        existing.update(row[0] for row in rows)
    return existing


def read_csv_rows(source_path: Path) -> list[dict[str, str]]:
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def format_usgs_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def fetch_usgs_rows(
    years: int,
    min_magnitude: float,
    chunk_days: int,
    request_timeout: int,
    max_retries: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=365 * years)
    chunk_size = timedelta(days=max(1, chunk_days))

    rows: list[dict[str, Any]] = []
    chunk_count = 0
    current_start = start_time

    while current_start < end_time:
        current_end = min(current_start + chunk_size, end_time)
        params = {
            "format": "geojson",
            "starttime": format_usgs_datetime(current_start),
            "endtime": format_usgs_datetime(current_end),
            "minmagnitude": min_magnitude,
            "orderby": "time-asc",
            "limit": 20000,
        }
        request_url = f"{config.USGS_EVENT_QUERY_URL}?{urlencode(params)}"
        payload = None
        request = Request(
            request_url,
            headers={
                "User-Agent": "earthquake-mvp/1.0 (+https://earthquake.usgs.gov/)",
                "Accept": "application/json",
            },
        )
        for attempt in range(1, max(1, max_retries) + 1):
            try:
                with urlopen(request, timeout=request_timeout) as response:
                    payload = json.load(response)
                break
            except Exception:
                if attempt >= max(1, max_retries):
                    raise
                time.sleep(min(2 * attempt, 5))
        if payload is None:
            raise RuntimeError("failed to fetch USGS payload")
        rows.extend(payload.get("features", []))
        chunk_count += 1
        current_start = current_end

    return rows, {
        "source_url": config.USGS_EVENT_QUERY_URL,
        "usgs_min_magnitude": min_magnitude,
        "usgs_chunk_days": max(1, chunk_days),
        "usgs_max_retries": max(1, max_retries),
        "fetched_chunks": chunk_count,
    }


def normalize_usgs_feature(feature: dict[str, Any], source_name: str) -> dict[str, Any]:
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    if len(coordinates) < 2:
        raise ValueError("missing coordinates")

    event_time_ms = properties.get("time")
    if event_time_ms is None:
        raise ValueError("missing event time")
    event_time = datetime.fromtimestamp(event_time_ms / 1000, tz=timezone.utc)
    normalized_time = event_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    latitude = float(coordinates[1])
    longitude = float(coordinates[0])
    depth = float(coordinates[2]) if len(coordinates) > 2 and coordinates[2] is not None else None
    magnitude = float(properties["mag"])
    region = str(properties.get("place") or "UNKNOWN").strip() or "UNKNOWN"
    source_event_id = str(feature.get("id") or properties.get("code") or "").strip()
    if not source_event_id:
        source_event_id = build_fallback_id(normalized_time, latitude, longitude, magnitude, region)
    unid = f"{source_name}_{source_event_id}"

    return {
        "unid": unid,
        "time": normalized_time,
        "event_time": event_time,
        "latitude": latitude,
        "longitude": longitude,
        "depth": depth,
        "magnitude": magnitude,
        "region": region,
        "source": source_name,
        "source_event_id": source_event_id,
        "is_realtime": False,
    }


def import_history(
    source_type: str,
    source_path: Path,
    source_name: str,
    years: int,
    batch_size: int,
    usgs_min_magnitude: float,
    usgs_chunk_days: int,
    request_timeout: int,
    max_retries: int,
) -> dict[str, Any]:
    if source_type == "csv":
        if not source_path.exists():
            raise FileNotFoundError(f"history source not found: {source_path}")
        raw_rows: list[Any] = read_csv_rows(source_path)
        source_meta = {"source_path": str(source_path)}
        normalizer = lambda row: normalize_row(row, source_name)
    else:
        raw_rows, source_meta = fetch_usgs_rows(
            years=years,
            min_magnitude=usgs_min_magnitude,
            chunk_days=usgs_chunk_days,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        normalizer = lambda row: normalize_usgs_feature(row, source_name)

    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * years)

    stats: dict[str, Any] = {
        "source_type": source_type,
        "source_name": source_name,
        "years": years,
        "fetched_rows": len(raw_rows),
        "filtered_in_range": 0,
        "inserted_rows": 0,
        "skipped_existing": 0,
        "skipped_duplicate_in_file": 0,
        "skipped_out_of_range": 0,
        "failed_rows": 0,
    }
    stats.update(source_meta)

    normalized_rows: list[dict[str, Any]] = []
    seen_in_file: set[str] = set()

    for row in raw_rows:
        try:
            normalized = normalizer(row)
        except Exception:
            stats["failed_rows"] += 1
            continue

        if normalized["event_time"] < cutoff:
            stats["skipped_out_of_range"] += 1
            continue

        if normalized["unid"] in seen_in_file:
            stats["skipped_duplicate_in_file"] += 1
            continue

        seen_in_file.add(normalized["unid"])
        normalized_rows.append(normalized)

    stats["filtered_in_range"] = len(normalized_rows)
    if not normalized_rows:
        return stats

    conn = duckdb.connect(str(config.DATABASE_PATH), read_only=False)
    try:
        database.load_extensions(conn, set(config.DUCKDB_EXTENSIONS))
        existing_unids = load_existing_unids(
            conn,
            [row["unid"] for row in normalized_rows],
            max(1, batch_size),
        )

        for row in normalized_rows:
            if row["unid"] in existing_unids:
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
            existing_unids.add(row["unid"])
    finally:
        conn.close()

    return stats


def main() -> int:
    args = parse_args()
    stats = import_history(
        source_type=args.source_type,
        source_path=args.source_path,
        source_name=args.source_name,
        years=args.years,
        batch_size=args.batch_size,
        usgs_min_magnitude=args.usgs_min_magnitude,
        usgs_chunk_days=args.usgs_chunk_days,
        request_timeout=args.request_timeout,
        max_retries=args.max_retries,
    )

    print("[HISTORY_IMPORT]")
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

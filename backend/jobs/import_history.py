"""Import historical earthquake records from a local CSV file."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
    parser = argparse.ArgumentParser(description="Import historical earthquakes from a CSV file.")
    parser.add_argument(
        "--source-path",
        type=Path,
        default=config.DEFAULT_HISTORY_IMPORT_SOURCE_PATH,
        help="Path to the history CSV file.",
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


def import_history(
    source_path: Path,
    source_name: str,
    years: int,
    batch_size: int,
) -> dict[str, Any]:
    if not source_path.exists():
        raise FileNotFoundError(f"history source not found: {source_path}")

    raw_rows = read_csv_rows(source_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * years)

    stats: dict[str, Any] = {
        "source_path": str(source_path),
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

    normalized_rows: list[dict[str, Any]] = []
    seen_in_file: set[str] = set()

    for row in raw_rows:
        try:
            normalized = normalize_row(row, source_name)
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
        source_path=args.source_path,
        source_name=args.source_name,
        years=args.years,
        batch_size=args.batch_size,
    )

    print("[HISTORY_IMPORT]")
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

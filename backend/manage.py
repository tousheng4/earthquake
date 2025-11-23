"""Convenience script to init DB, import CSV data, and run the API server."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

import database


def init_db() -> None:
    database.init_db()
    print("[OK] Database initialized.")


def import_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            quake = {
                "unid": row.get("unid") or row.get("UNID"),
                "time": row.get("time") or row.get("TIME"),
                "latitude": float(row["latitude"] or row["LATITUDE"]),
                "longitude": float(row["longitude"] or row["LONGITUDE"]),
                "depth": (
                    float(row["depth"])
                    if row.get("depth")
                    else float(row["DEPTH"])
                    if row.get("DEPTH")
                    else None
                ),
                "magnitude": float(row.get("magnitude") or row.get("MAGNITUDE")),
                "region": row.get("region") or row.get("REGION", ""),
            }
            if not quake["unid"]:
                continue
            database.insert_earthquake(quake)
            count += 1
    print(f"[OK] Imported {count} rows from {csv_path}.")


def run_server(host: str, port: int, debug: bool) -> None:
    from api import app  # Imported lazily so CLI runners can skip Flask deps

    print(f"[INFO] Starting Flask server on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage earthquake backend.")
    parser.add_argument(
        "--csv",
        type=Path,
        help="Path to CSV file to import (default: backend/earthquakes.csv if exists).",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the Flask API server after initialization/import.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run Flask server in debug mode (defaults to False).",
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip init_db step (assume DB schema already prepared).",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])

    try:
        if not args.skip_init:
            init_db()

        csv_path = args.csv
        if csv_path is None:
            default_csv = Path(__file__).with_name("earthquakes.csv")
            if default_csv.exists():
                csv_path = default_csv

        if csv_path is not None:
            import_csv(csv_path)

        if args.serve:
            run_server(host=args.host, port=args.port, debug=args.debug)
        else:
            print("[DONE] All requested tasks completed.")
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

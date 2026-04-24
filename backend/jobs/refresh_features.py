"""Refresh earthquake event features for a recent time window."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from analysis.feature_builder import build_feature_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh earthquake event features.")
    parser.add_argument(
        "--hours",
        type=int,
        default=config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS,
        help="Only refresh features for events within the most recent N hours.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=config.DEFAULT_FEATURE_BATCH_LIMIT,
        help="Maximum number of recent events to process in one run.",
    )
    parser.add_argument(
        "--baseline-years",
        type=int,
        default=config.DEFAULT_FEATURE_BASELINE_YEARS,
        help="Historical baseline span used when building feature rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = time.perf_counter()
    stats = build_feature_rows(
        hours=args.hours,
        limit=args.limit,
        baseline_years=args.baseline_years,
    )
    stats["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)

    print("[FEATURE_REFRESH]")
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

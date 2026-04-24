"""Score earthquake risk from cached event features."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from analysis.risk_scorer import score_recent_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score earthquake risk from cached features.")
    parser.add_argument(
        "--limit",
        type=int,
        default=config.DEFAULT_FEATURE_BATCH_LIMIT,
        help="Maximum number of feature rows to score in one run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = time.perf_counter()
    stats = score_recent_features(limit=args.limit)
    stats["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)

    print("[RISK_SCORE]")
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

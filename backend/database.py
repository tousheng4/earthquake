from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import duckdb

DB_PATH = Path(__file__).resolve().with_name("earthquakes.duckdb")
logger = logging.getLogger(__name__)


def get_db_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """获取 DuckDB 连接。"""
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def init_db() -> None:
    """初始化数据库表。"""
    try:
        conn = get_db_connection(read_only=False)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earthquakes (
                unid VARCHAR PRIMARY KEY,
                time VARCHAR NOT NULL,
                latitude DOUBLE,
                longitude DOUBLE,
                depth DOUBLE,
                magnitude DOUBLE,
                region VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    finally:
        conn.close()


def insert_earthquake(data: Dict[str, Any]) -> bool:
    """插入一条地震数据，如果存在则忽略。"""
    try:
        conn = get_db_connection(read_only=False)
    except Exception:
        logger.exception("Error connecting to DB for write")
        return False

    try:
        query = """
            INSERT INTO earthquakes (unid, time, latitude, longitude, depth, magnitude, region)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (unid) DO NOTHING
        """
        params: Iterable[Any] = (
            data["unid"],
            data["time"],
            data["latitude"],
            data["longitude"],
            data.get("depth"),
            data["magnitude"],
            data["region"],
        )
        conn.execute(query, params)
        return True
    except Exception:
        logger.exception("Error inserting earthquake")
        return False
    finally:
        conn.close()


def get_recent_earthquakes(hours: int = 48) -> List[Dict[str, Any]]:
    """获取最近 N 小时的地震数据。"""
    try:
        conn = get_db_connection(read_only=True)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        result = conn.execute(
            "SELECT * FROM earthquakes WHERE time > ? ORDER BY time DESC",
            [cutoff_str],
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def get_all_unids() -> Set[str]:
    """获取所有已存在的 UNID，用于初始化缓存。"""
    try:
        conn = get_db_connection(read_only=True)
    except Exception:
        return set()

    try:
        result = conn.execute("SELECT unid FROM earthquakes").fetchall()
        return {row[0] for row in result}
    finally:
        conn.close()

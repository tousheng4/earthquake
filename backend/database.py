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


def _ensure_spatial(conn: duckdb.DuckDBPyConnection) -> None:
    """安装并加载 spatial 扩展（幂等）。"""
    try:
        conn.execute("INSTALL spatial")
    except Exception:
        logger.debug("Spatial extension install skipped/failed (possibly already installed).")
    conn.execute("LOAD spatial")


def _ensure_geom_column(conn: duckdb.DuckDBPyConnection) -> None:
    """确保表存在 geom 列并填充已有数据。"""
    try:
        conn.execute("DESCRIBE earthquakes")
    except Exception:
        # 表尚未创建
        return

    try:
        conn.execute("ALTER TABLE earthquakes ADD COLUMN geom GEOMETRY")
    except Exception:
        # 列已存在则忽略
        pass

    conn.execute(
        """
        UPDATE earthquakes
        SET geom = ST_Point(longitude, latitude)
        WHERE geom IS NULL AND longitude IS NOT NULL AND latitude IS NOT NULL
        """
    )

    try:
        conn.execute("CREATE INDEX idx_earthquakes_geom ON earthquakes USING RTREE (geom)")
    except Exception:
        # 索引已存在则忽略
        pass


def init_db() -> None:
    """初始化数据库表。"""
    try:
        conn = get_db_connection(read_only=False)
        _ensure_spatial(conn)
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
                geom GEOMETRY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_geom_column(conn)
    finally:
        conn.close()


def insert_earthquake(data: Dict[str, Any]) -> bool:
    """插入一条地震数据，如果存在则忽略。"""
    try:
        conn = get_db_connection(read_only=False)
        _ensure_spatial(conn)
        _ensure_geom_column(conn)
    except Exception:
        logger.exception("Error connecting to DB for write")
        return False

    try:
        query = """
            INSERT INTO earthquakes (unid, time, latitude, longitude, depth, magnitude, region, geom)
            VALUES (?, ?, ?, ?, ?, ?, ?, ST_Point(?, ?))
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
            data["longitude"],
            data["latitude"],
        )
        conn.execute(query, params)
        return True
    except Exception:
        logger.exception("Error inserting earthquake")
        return False
    finally:
        conn.close()


def _rows_to_dicts(result: duckdb.DuckDBPyRelation) -> List[Dict[str, Any]]:
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    dicts = []
    for row in rows:
        d = {}
        for col, val in zip(columns, row):
            # 跳过 bytes 类型的几何字段，因为它们无法被 JSON 序列化
            if isinstance(val, bytes):
                continue
            d[col] = val
        dicts.append(d)
    return dicts


def get_recent_earthquakes(hours: int = 48) -> List[Dict[str, Any]]:
    """获取最近 N 小时的地震数据。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
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
        return _rows_to_dicts(result)
    finally:
        conn.close()


def query_within_radius(
    lon: float,
    lat: float,
    radius_km: float,
    hours: int = 48,
) -> List[Dict[str, Any]]:
    """按圆形范围查询（半径 km）。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        radius_m = radius_km * 1000

        result = conn.execute(
            """
            SELECT * FROM earthquakes
            WHERE time > ?
              AND geom IS NOT NULL
              AND ST_DWithin(
                    CAST(geom AS GEOGRAPHY),
                    CAST(ST_Point(?, ?) AS GEOGRAPHY),
                    ?
              )
            ORDER BY time DESC
            """,
            [cutoff_str, lon, lat, radius_m],
        )
        return _rows_to_dicts(result)
    finally:
        conn.close()


def query_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    hours: int = 48,
) -> List[Dict[str, Any]]:
    """按矩形范围查询。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        result = conn.execute(
            """
            SELECT * FROM earthquakes
            WHERE time > ?
              AND geom IS NOT NULL
              AND ST_Intersects(
                    geom,
                    ST_MakeEnvelope(?, ?, ?, ?, 4326)
              )
            ORDER BY time DESC
            """,
            [cutoff_str, min_lon, min_lat, max_lon, max_lat],
        )
        return _rows_to_dicts(result)
    finally:
        conn.close()


def query_overlay(geom_text: str, hours: int = 48) -> List[Dict[str, Any]]:
    """叠加分析，返回与输入几何相交的地震点。支持 WKT 或 GeoJSON。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if geom_text.strip().startswith("{"):
            geom_expr = "ST_GeomFromGeoJSON(?)"
        else:
            geom_expr = "ST_GeomFromText(?)"

        result = conn.execute(
            f"""
            SELECT * FROM earthquakes
            WHERE time > ?
              AND geom IS NOT NULL
              AND ST_Intersects(geom, {geom_expr})
            ORDER BY time DESC
            """,
            [cutoff_str, geom_text],
        )
        return _rows_to_dicts(result)
    finally:
        conn.close()


def query_nearest(
    lon: float,
    lat: float,
    limit: int = 10,
    hours: int = 24 * 30,
) -> List[Dict[str, Any]]:
    """最近邻查询，按距离排序返回指定数量。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        result = conn.execute(
            """
            SELECT *, ST_Distance_Sphere(geom, ST_Point(?, ?)) AS distance_m
            FROM earthquakes
            WHERE time > ? AND geom IS NOT NULL
            ORDER BY distance_m ASC
            LIMIT ?
            """,
            [lon, lat, cutoff_str, limit],
        )
        return _rows_to_dicts(result)
    finally:
        conn.close()


def buffered_events(radius_km: float, hours: int = 48) -> List[Dict[str, Any]]:
    """返回按时间筛选后的地震，并给出缓冲区几何的 GeoJSON。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        radius_m = radius_km * 1000

        result = conn.execute(
            """
            SELECT
                unid, time, latitude, longitude, depth, magnitude, region,
                ST_AsGeoJSON(
                    ST_Buffer(
                        CAST(geom AS GEOGRAPHY),
                        ?
                    )::GEOMETRY
                ) AS buffer_geojson
            FROM earthquakes
            WHERE time > ? AND geom IS NOT NULL
            """,
            [radius_m, cutoff_str],
        )
        return _rows_to_dicts(result)
    finally:
        conn.close()


def cluster_grid(cell_km: float = 50, hours: int = 48) -> List[Dict[str, Any]]:
    """基于简单网格的聚类统计，返回格网中心和数量。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        step_deg = cell_km / 111.0

        result = conn.execute(
            """
            WITH bucketed AS (
                SELECT
                    FLOOR(longitude / ?) AS lon_bin,
                    FLOOR(latitude / ?) AS lat_bin,
                    longitude,
                    latitude,
                    magnitude,
                    time
                FROM earthquakes
                WHERE time > ? AND geom IS NOT NULL
            )
            SELECT
                lon_bin,
                lat_bin,
                COUNT(*) AS count,
                AVG(magnitude) AS avg_magnitude,
                MIN(time) AS min_time,
                MAX(time) AS max_time,
                AVG(longitude) AS center_lon,
                AVG(latitude) AS center_lat
            FROM bucketed
            GROUP BY lon_bin, lat_bin
            HAVING count > 0
            ORDER BY count DESC
            """,
            [step_deg, step_deg, cutoff_str],
        )
        return _rows_to_dicts(result)
    finally:
        conn.close()


def get_time_window(
    start_iso: str | None = None,
    end_iso: str | None = None,
    limit: int = 2000,
) -> List[Dict[str, Any]]:
    """按时间窗口获取地震（用于轨迹/时间动画）。"""
    try:
        conn = get_db_connection(read_only=True)
        _ensure_spatial(conn)
    except Exception:
        logger.exception("Error connecting to DB (read-only)")
        return []

    try:
        params: List[Any] = []
        clauses = []
        if start_iso:
            clauses.append("time >= ?")
            params.append(start_iso)
        if end_iso:
            clauses.append("time <= ?")
            params.append(end_iso)

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        result = conn.execute(
            f"""
            SELECT * FROM earthquakes
            {where_sql}
            ORDER BY time ASC
            LIMIT ?
            """,
            [*params, limit],
        )
        return _rows_to_dicts(result)
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

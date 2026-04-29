import json
import logging
import math
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import duckdb
import config

DB_PATH = config.DATABASE_PATH
DEFAULT_EXTENSIONS: Set[str] = set(config.DUCKDB_EXTENSIONS)
logger = logging.getLogger(__name__)
_connection_pool: "SingleConnectionPool | None" = None


def load_extensions(conn: duckdb.DuckDBPyConnection, extensions: Set[str]) -> duckdb.DuckDBPyConnection:
    for ext in extensions:
        conn.execute(f"INSTALL {ext}")
        conn.execute(f"LOAD {ext}")
    return conn


def get_db_connection(read_only: bool = False, extensions: Set[str] | None = None) -> duckdb.DuckDBPyConnection:
    """获取 DuckDB 连接，并确保空间扩展可用。"""
    conn = duckdb.connect(str(DB_PATH), read_only=read_only)
    conn = load_extensions(conn, extensions or DEFAULT_EXTENSIONS)
    return conn

class SingleConnectionPool:
    """只创建并复用一个 DuckDB 连接，使用锁串行化访问。"""

    def __init__(self, db_path: Path | None = None, extensions: Set[str] | None = None):
        self.db_path = db_path or DB_PATH
        self.extensions = extensions or DEFAULT_EXTENSIONS
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.RLock()

    def _ensure_connection(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            conn = duckdb.connect(str(self.db_path), read_only=False)
            load_extensions(conn, self.extensions)
            self._conn = conn
        return self._conn

    @contextmanager
    def acquire(self, extra_extensions: Set[str] | None = None) -> Iterable[duckdb.DuckDBPyConnection]:
        with self._lock:
            conn = self._ensure_connection()
            if extra_extensions:
                load_extensions(conn, extra_extensions)
            yield conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


@contextmanager
def _connection_scope(read_only: bool = False, extensions: Set[str] | None = None) -> Iterable[duckdb.DuckDBPyConnection]:
    """统一的连接上下文，如果存在池则复用单连接。"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = SingleConnectionPool()
    pool = _connection_pool
    with pool.acquire(extensions) as conn:
        yield conn


def _cutoff_iso(hours: int) -> str:
    """返回距现在 N 小时的 ISO 字符串。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class EarthquakeQuery:
    """地震数据查询构建器。"""
    
    def __init__(self):
        self._where_clauses: List[str] = []
        self._params: List[Any] = []
        self._select_fields: str = "*"
        self._order_by: str = "time DESC"
        self._limit: Optional[int] = None
        self._require_geom: bool = False
    
    def select(self, fields: str) -> "EarthquakeQuery":
        """指定 SELECT 字段。"""
        self._select_fields = fields
        return self
    
    def since(self, hours: int) -> "EarthquakeQuery":
        """筛选最近 N 小时的数据。"""
        self._where_clauses.append("time > ?")
        self._params.append(_cutoff_iso(hours))
        return self
    
    def time_range(self, start_iso: Optional[str] = None, end_iso: Optional[str] = None) -> "EarthquakeQuery":
        """筛选时间范围。"""
        if start_iso:
            self._where_clauses.append("time >= ?")
            self._params.append(start_iso)
        if end_iso:
            self._where_clauses.append("time <= ?")
            self._params.append(end_iso)
        return self
    
    def within_radius(self, lon: float, lat: float, radius_km: float) -> "EarthquakeQuery":
        """按圆形范围筛选（半径 km）。"""
        radius_m = radius_km * 1000
        self._where_clauses.append(
            """ST_DWithin(
                CAST(geom AS GEOGRAPHY),
                CAST(ST_Point(?, ?) AS GEOGRAPHY),
                ?
            )"""
        )
        self._params.extend([lon, lat, radius_m])
        self._require_geom = True
        return self
    
    def in_bbox(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> "EarthquakeQuery":
        """按矩形范围筛选。"""
        self._where_clauses.append(
            "ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?, 4326))"
        )
        self._params.extend([min_lon, min_lat, max_lon, max_lat])
        self._require_geom = True
        return self
    
    def intersects(self, geom_text: str) -> "EarthquakeQuery":
        """与指定几何相交（支持 WKT 或 GeoJSON）。"""
        if geom_text.strip().startswith("{"):
            geom_expr = "ST_GeomFromGeoJSON(?)"
        else:
            geom_expr = "ST_GeomFromText(?)"
        self._where_clauses.append(f"ST_Intersects(geom, {geom_expr})")
        self._params.append(geom_text)
        self._require_geom = True
        return self
    
    def nearest(self, lon: float, lat: float, limit: int = 10) -> "EarthquakeQuery":
        """最近邻查询。"""
        self._select_fields = "*, ST_Distance_Sphere(geom, ST_Point(?, ?)) AS distance_m"
        self._params = [lat, lon] + self._params
        self._order_by = "distance_m ASC"
        self._limit = limit
        self._require_geom = True
        return self
    
    def order_by(self, order: str) -> "EarthquakeQuery":
        """指定排序。"""
        self._order_by = order
        return self
    
    def limit(self, n: int) -> "EarthquakeQuery":
        """限制结果数量。"""
        self._limit = n
        return self
    
    def _build_sql(self) -> Tuple[str, List[Any]]:
        """构建最终的 SQL 语句。"""
        # 处理 SELECT 中的参数（如 nearest 查询）
        select_params = []
        if "ST_Distance_Sphere" in self._select_fields:
            # 提取前两个参数用于 SELECT
            select_params = self._params[:2]
            where_params = self._params[2:]
        else:
            where_params = self._params
        
        sql_parts = [f"SELECT {self._select_fields} FROM earthquakes"]
        
        where_clauses = self._where_clauses.copy()
        if self._require_geom:
            where_clauses.insert(0, "geom IS NOT NULL")
        
        if where_clauses:
            sql_parts.append("WHERE " + " AND ".join(where_clauses))
        
        sql_parts.append(f"ORDER BY {self._order_by}")
        
        if self._limit:
            sql_parts.append(f"LIMIT {self._limit}")
        
        sql = "\n".join(sql_parts)
        params = select_params + where_params
        
        return sql, params
    
    def execute(self) -> List[Dict[str, Any]]:
        """执行查询并返回字典列表。"""
        sql, params = self._build_sql()
        try:
            with _connection_scope(read_only=True) as conn:
                df = conn.execute(sql, params).df()
                if "geom" in df.columns:
                    df = df.drop(columns=["geom"])
                return df.to_dict(orient="records")
        except Exception:
            logger.exception("Error executing query")
            return []
    
    def to_geojson(self) -> Dict[str, Any]:
        """执行查询并返回 GeoJSON FeatureCollection。"""
        sql, params = self._build_sql()
        
        # 包装为 GeoJSON 生成查询
        geojson_sql = f"""
        SELECT json_object(
            'type', 'FeatureCollection',
            'features', json_group_array(
                json_object(
                    'type', 'Feature',
                    'geometry', json(ST_AsGeoJSON(geom)),
                    'properties', json_object(
                        'unid', unid,
                        'time', "time",
                        'latitude', latitude,
                        'longitude', longitude,
                        'depth', depth,
                        'magnitude', magnitude,
                        'region', region
                    )
                )
            )
        ) as geojson
        FROM ({sql})
        WHERE geom IS NOT NULL
        """
        try:
            with _connection_scope(read_only=True) as conn:
                result = conn.execute(geojson_sql, params).fetchone()
                return json.loads(result[0]) if result and result[0] else {"type": "FeatureCollection", "features": []}
        except Exception:
            logger.exception("Error executing GeoJSON query")
            return {"type": "FeatureCollection", "features": []}
    
    def to_sql(self) -> Tuple[str, List[Any]]:
        """返回 SQL 语句和参数（用于调试）。"""
        return self._build_sql()


def insert_earthquake(data: Dict[str, Any]) -> bool:
    """插入一条地震数据，如果存在则忽略。"""
    query = """
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
    params: Iterable[Any] = (
        data["unid"],
        data["time"],
        data["latitude"],
        data["longitude"],
        data.get("depth"),
        data["magnitude"],
        data["region"],
        data.get("source", "emsc"),
        data.get("source_event_id", data["unid"]),
        data.get("is_realtime", True),
        data["longitude"],
        data["latitude"],
    )
    try:
        with _connection_scope(read_only=False) as conn:
            conn.execute(query, params)
        return True
    except Exception:
        logger.exception("Error inserting earthquake")
        return False


# ========== 向后兼容的便捷函数 ==========

def get_recent_earthquakes(hours: int = 48) -> List[Dict[str, Any]]:
    """获取最近 N 小时的地震数据。"""
    return EarthquakeQuery().since(hours).execute()


def query_within_radius(
    lon: float,
    lat: float,
    radius_km: float,
    hours: int = 48,
) -> List[Dict[str, Any]]:
    """按圆形范围查询（半径 km）。"""
    return EarthquakeQuery().since(hours).within_radius(lon, lat, radius_km).execute()


def query_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    hours: int = 48,
) -> List[Dict[str, Any]]:
    """按矩形范围查询。"""
    return EarthquakeQuery().since(hours).in_bbox(min_lon, min_lat, max_lon, max_lat).execute()


def query_overlay(geom_text: str, hours: int = 48) -> List[Dict[str, Any]]:
    """叠加分析，返回与输入几何相交的地震点。支持 WKT 或 GeoJSON。"""
    return EarthquakeQuery().since(hours).intersects(geom_text).execute()


def query_nearest(
    lon: float,
    lat: float,
    limit: int = 10,
    hours: int = config.DEFAULT_NEAREST_LOOKBACK_HOURS,
) -> List[Dict[str, Any]]:
    """最近邻查询，按距离排序返回指定数量。"""
    query = """
        SELECT
            *,
            6371000 * 2 * ASIN(
                SQRT(
                    POWER(SIN(RADIANS(latitude - ?) / 2), 2)
                    + COS(RADIANS(?))
                    * COS(RADIANS(latitude))
                    * POWER(SIN(RADIANS(longitude - ?) / 2), 2)
                )
            ) AS distance_m
        FROM earthquakes
        WHERE time > ? AND latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY distance_m ASC
        LIMIT ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(query, [lat, lat, lon, _cutoff_iso(hours), limit])
            df = result.df()
            if "geom" in df.columns:
                df = df.drop(columns=["geom"])
            return df.to_dict(orient="records")
    except Exception:
        logger.exception("Error executing query_nearest")
        return []


def buffered_events(
    radius_km: float,
    hours: int = 48,
    event_unid: str | None = None,
) -> List[Dict[str, Any]]:
    """返回按时间筛选后的地震，并给出缓冲区几何的 GeoJSON。"""
    where_clauses = ["time > ?", "latitude IS NOT NULL", "longitude IS NOT NULL"]
    params: List[Any] = [_cutoff_iso(hours)]
    if event_unid:
        where_clauses.append("unid = ?")
        params.append(event_unid)

    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(
                f"""
                SELECT
                    unid, time, latitude, longitude, depth, magnitude, region
                FROM earthquakes
                WHERE {" AND ".join(where_clauses)}
                """,
                params,
            )
            rows = result.df().to_dict(orient="records")
            for row in rows:
                row["buffer_geojson"] = json.dumps(
                    _circle_polygon_geojson(
                        lon=float(row["longitude"]),
                        lat=float(row["latitude"]),
                        radius_km=radius_km,
                    )
                )
            return rows
    except Exception:
        logger.exception("Error executing buffered_events query")
        return []


def _circle_polygon_geojson(
    lon: float,
    lat: float,
    radius_km: float,
    segments: int = 72,
) -> Dict[str, Any]:
    """Build an approximate geodesic circle polygon around a lon/lat point."""
    earth_radius_km = 6371.0
    angular_distance = radius_km / earth_radius_km
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    ring: List[List[float]] = []

    for index in range(segments + 1):
        bearing = math.radians((360.0 * index) / segments)
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular_distance)
            + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
        )
        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
            math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
        )
        point_lon = ((math.degrees(lon2) + 540.0) % 360.0) - 180.0
        point_lat = math.degrees(lat2)
        ring.append([round(point_lon, 6), round(point_lat, 6)])

    return {"type": "Polygon", "coordinates": [ring]}


def cluster_grid(cell_km: float = 50, hours: int = 48) -> List[Dict[str, Any]]:
    """基于简单网格的聚类统计，返回格网中心和数量。"""
    step_deg = cell_km / 111.0
    try:
        with _connection_scope(read_only=True) as conn:
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
                [step_deg, step_deg, _cutoff_iso(hours)],
            )
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing cluster_grid query")
        return []


def get_time_window(
    start_iso: str | None = None,
    end_iso: str | None = None,
    limit: int = 2000,
) -> List[Dict[str, Any]]:
    """按时间窗口获取地震（用于轨迹/时间动画）。"""
    query = EarthquakeQuery().time_range(start_iso, end_iso).order_by("time ASC").limit(limit)
    return query.execute()


def region_statistics(
    min_lon: float | None = None,
    min_lat: float | None = None,
    max_lon: float | None = None,
    max_lat: float | None = None,
    lon: float | None = None,
    lat: float | None = None,
    radius_km: float | None = None,
    hours: int = 48,
) -> Dict[str, Any]:
    """区域统计：返回地震频次、平均震级、最高震级、深度统计等。"""
    query = EarthquakeQuery().since(hours)

    if lon is not None and lat is not None and radius_km is not None:
        query = query.within_radius(lon, lat, radius_km)
    elif None not in (min_lon, min_lat, max_lon, max_lat):
        query = query.in_bbox(min_lon, min_lat, max_lon, max_lat)
    else:
        # 无空间过滤，使用全部数据
        pass

    sql = f"""
        SELECT
            COUNT(*) AS total_count,
            AVG(magnitude) AS avg_magnitude,
            MAX(magnitude) AS max_magnitude,
            MIN(magnitude) AS min_magnitude,
            AVG(depth) AS avg_depth,
            MIN(depth) AS min_depth,
            MAX(depth) AS max_depth
        FROM earthquakes
        WHERE time > ?
    """

    params = [_cutoff_iso(hours)]

    # 添加空间过滤条件
    if lon is not None and lat is not None and radius_km is not None:
        radius_m = radius_km * 1000
        sql += f"""
            AND ST_DWithin(
                CAST(geom AS GEOGRAPHY),
                CAST(ST_Point(?, ?) AS GEOGRAPHY),
                ?
            )
        """
        params = [lon, lat, radius_m] + params
    elif None not in (min_lon, min_lat, max_lon, max_lat):
        sql += """
            AND ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?, 4326))
        """
        params = [min_lon, min_lat, max_lon, max_lat] + params

    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(sql, params).fetchone()
            if result:
                return {
                    "total_count": result[0] or 0,
                    "avg_magnitude": round(result[1], 2) if result[1] else 0,
                    "max_magnitude": result[2] or 0,
                    "min_magnitude": result[3] or 0,
                    "avg_depth": round(result[4], 2) if result[4] else 0,
                    "min_depth": result[5] or 0,
                    "max_depth": result[6] or 0,
                }
    except Exception:
        logger.exception("Error executing region_statistics")
    return {"total_count": 0, "avg_magnitude": 0, "max_magnitude": 0, "min_magnitude": 0,
            "avg_depth": 0, "min_depth": 0, "max_depth": 0}


def magnitude_distribution(
    min_lon: float | None = None,
    min_lat: float | None = None,
    max_lon: float | None = None,
    max_lat: float | None = None,
    hours: int = 48,
    bins: list[float] | None = None,
) -> List[Dict[str, Any]]:
    """按震级区间统计频次分布（用于柱状图）。"""
    if bins is None:
        bins = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]  # 默认区间

    query = EarthquakeQuery().since(hours)

    if None not in (min_lon, min_lat, max_lon, max_lat):
        query = query.in_bbox(min_lon, min_lat, max_lon, max_lat)

    sql_parts = [f"SELECT magnitude FROM earthquakes WHERE time > ?"]
    params = [_cutoff_iso(hours)]

    if None not in (min_lon, min_lat, max_lon, max_lat):
        sql_parts.append("AND ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?, 4326))")
        params = [min_lon, min_lat, max_lon, max_lat] + params

    sql = " AND ".join(sql_parts)

    try:
        with _connection_scope(read_only=True) as conn:
            df = conn.execute(sql, params).df()
            magnitudes = df["magnitude"].tolist()

        # 统计各区间频次
        result = []
        for i in range(len(bins) - 1):
            count = sum(1 for m in magnitudes if bins[i] <= m < bins[i + 1])
            result.append({
                "range": f"{bins[i]}-{bins[i+1]}",
                "count": count,
                "bin_start": bins[i],
                "bin_end": bins[i + 1]
            })
        # 最后一个区间上限开放
        count = sum(1 for m in magnitudes if m >= bins[-1])
        result.append({
            "range": f">{bins[-1]}",
            "count": count,
            "bin_start": bins[-1],
            "bin_end": None
        })

        return result
    except Exception:
        logger.exception("Error executing magnitude_distribution")
    return []


def hourly_distribution(hours: int = 48) -> List[Dict[str, Any]]:
    """按小时统计地震频次分布（用于24小时折线图）。"""
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(
                """
                SELECT
                    CAST(strftime('%H', time) AS INTEGER) AS hour,
                    COUNT(*) AS count,
                    AVG(magnitude) AS avg_magnitude
                FROM earthquakes
                WHERE time > ?
                GROUP BY hour
                ORDER BY hour
                """,
                [_cutoff_iso(hours)],
            )
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing hourly_distribution")
    return []


def history_timeline(
    years: int = config.DEFAULT_HISTORY_IMPORT_YEARS,
    bucket: str = "month",
) -> List[Dict[str, Any]]:
    """Aggregate historical earthquakes by month or day."""
    bucket = bucket.lower()
    if bucket not in {"month", "day"}:
        bucket = "month"

    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(
                f"""
                SELECT
                    strftime(date_trunc('{bucket}', CAST(time AS TIMESTAMP)), '%Y-%m-%d') AS bucket_start,
                    COUNT(*) AS event_count
                FROM earthquakes
                WHERE
                    CAST(time AS TIMESTAMP) >= now() - (? * INTERVAL '1 year')
                    AND is_realtime = false
                GROUP BY 1
                ORDER BY bucket_start ASC
                """,
                [years],
            )
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing history_timeline")
    return []


def history_region_distribution(
    years: int = config.DEFAULT_HISTORY_IMPORT_YEARS,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Aggregate historical earthquakes by region."""
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(region, ''), 'UNKNOWN') AS region,
                    COUNT(*) AS event_count
                FROM earthquakes
                WHERE
                    CAST(time AS TIMESTAMP) >= now() - (? * INTERVAL '1 year')
                    AND is_realtime = false
                GROUP BY 1
                ORDER BY event_count DESC, region ASC
                LIMIT ?
                """,
                [years, limit],
            )
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing history_region_distribution")
    return []


FEATURE_UPSERT_SQL = """
    INSERT INTO earthquake_features (
        event_unid,
        event_time,
        region,
        magnitude,
        depth,
        recent_window_hours,
        recent_region_event_count,
        recent_region_avg_magnitude,
        historical_baseline_years,
        historical_region_event_count,
        historical_avg_daily_count,
        historical_daily_count_stddev,
        anomaly_score,
        feature_version,
        refreshed_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (event_unid) DO UPDATE SET
        event_time = EXCLUDED.event_time,
        region = EXCLUDED.region,
        magnitude = EXCLUDED.magnitude,
        depth = EXCLUDED.depth,
        recent_window_hours = EXCLUDED.recent_window_hours,
        recent_region_event_count = EXCLUDED.recent_region_event_count,
        recent_region_avg_magnitude = EXCLUDED.recent_region_avg_magnitude,
        historical_baseline_years = EXCLUDED.historical_baseline_years,
        historical_region_event_count = EXCLUDED.historical_region_event_count,
        historical_avg_daily_count = EXCLUDED.historical_avg_daily_count,
        historical_daily_count_stddev = EXCLUDED.historical_daily_count_stddev,
        anomaly_score = EXCLUDED.anomaly_score,
        feature_version = EXCLUDED.feature_version,
        refreshed_at = EXCLUDED.refreshed_at
"""


def list_feature_candidates(
    hours: int = config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS,
    limit: int = config.DEFAULT_FEATURE_BATCH_LIMIT,
) -> List[Dict[str, Any]]:
    """列出后续特征刷新优先处理的近期事件。"""
    query = """
        SELECT
            unid,
            CAST(time AS TIMESTAMP) AS time,
            latitude,
            longitude,
            depth,
            magnitude,
            COALESCE(NULLIF(region, ''), 'UNKNOWN') AS region,
            source,
            source_event_id,
            is_realtime
        FROM earthquakes
        WHERE CAST(time AS TIMESTAMP) >= now() - (? * INTERVAL '1 hour')
        ORDER BY CAST(time AS TIMESTAMP) DESC
        LIMIT ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(query, [hours, limit])
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing list_feature_candidates")
    return []


def upsert_earthquake_features(rows: List[Dict[str, Any]]) -> int:
    """批量写入或更新事件特征缓存。"""
    if not rows:
        return 0

    inserted = 0
    try:
        with _connection_scope(read_only=False) as conn:
            for row in rows:
                conn.execute(
                    FEATURE_UPSERT_SQL,
                    [
                        row["event_unid"],
                        row["event_time"],
                        row.get("region"),
                        row.get("magnitude"),
                        row.get("depth"),
                        row["recent_window_hours"],
                        row.get("recent_region_event_count"),
                        row.get("recent_region_avg_magnitude"),
                        row["historical_baseline_years"],
                        row.get("historical_region_event_count"),
                        row.get("historical_avg_daily_count"),
                        row.get("historical_daily_count_stddev"),
                        row.get("anomaly_score"),
                        row.get("feature_version", config.FEATURE_SCHEMA_VERSION),
                        row.get("refreshed_at", datetime.now(timezone.utc)),
                    ],
                )
                inserted += 1
        return inserted
    except Exception:
        logger.exception("Error executing upsert_earthquake_features")
    return 0


def get_event_feature(event_unid: str) -> Optional[Dict[str, Any]]:
    """读取单个事件的特征缓存。"""
    query = """
        SELECT
            event_unid,
            event_time,
            region,
            magnitude,
            depth,
            recent_window_hours,
            recent_region_event_count,
            recent_region_avg_magnitude,
            historical_baseline_years,
            historical_region_event_count,
            historical_avg_daily_count,
            historical_daily_count_stddev,
            anomaly_score,
            feature_version,
            refreshed_at
        FROM earthquake_features
        WHERE event_unid = ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            row = conn.execute(query, [event_unid]).fetchdf()
            if row.empty:
                return None
            return row.to_dict(orient="records")[0]
    except Exception:
        logger.exception("Error executing get_event_feature")
    return None


def list_event_features(limit: int = 20) -> List[Dict[str, Any]]:
    """列出最近刷新的一批事件特征。"""
    query = """
        SELECT
            event_unid,
            event_time,
            region,
            magnitude,
            depth,
            recent_window_hours,
            recent_region_event_count,
            recent_region_avg_magnitude,
            historical_baseline_years,
            historical_region_event_count,
            historical_avg_daily_count,
            historical_daily_count_stddev,
            anomaly_score,
            feature_version,
            refreshed_at
        FROM earthquake_features
        ORDER BY refreshed_at DESC, event_time DESC
        LIMIT ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(query, [limit])
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing list_event_features")
    return []


RISK_SCORE_UPSERT_SQL = """
    INSERT INTO earthquake_risk_scores (
        event_unid,
        event_time,
        region,
        risk_score,
        risk_level,
        magnitude_component,
        depth_component,
        activity_component,
        anomaly_component,
        explanation,
        score_version,
        scored_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (event_unid) DO UPDATE SET
        event_time = EXCLUDED.event_time,
        region = EXCLUDED.region,
        risk_score = EXCLUDED.risk_score,
        risk_level = EXCLUDED.risk_level,
        magnitude_component = EXCLUDED.magnitude_component,
        depth_component = EXCLUDED.depth_component,
        activity_component = EXCLUDED.activity_component,
        anomaly_component = EXCLUDED.anomaly_component,
        explanation = EXCLUDED.explanation,
        score_version = EXCLUDED.score_version,
        scored_at = EXCLUDED.scored_at
"""


def upsert_risk_scores(rows: List[Dict[str, Any]]) -> int:
    """批量写入或更新事件风险评分结果。"""
    if not rows:
        return 0

    inserted = 0
    try:
        with _connection_scope(read_only=False) as conn:
            for row in rows:
                conn.execute(
                    RISK_SCORE_UPSERT_SQL,
                    [
                        row["event_unid"],
                        row["event_time"],
                        row.get("region"),
                        row.get("risk_score"),
                        row.get("risk_level"),
                        row.get("magnitude_component"),
                        row.get("depth_component"),
                        row.get("activity_component"),
                        row.get("anomaly_component"),
                        row.get("explanation"),
                        row.get("score_version", config.RISK_SCHEMA_VERSION),
                        row.get("scored_at", datetime.now(timezone.utc)),
                    ],
                )
                inserted += 1
        return inserted
    except Exception:
        logger.exception("Error executing upsert_risk_scores")
    return 0


def get_risk_score(event_unid: str) -> Optional[Dict[str, Any]]:
    """读取单个事件的风险评分结果。"""
    query = """
        SELECT
            event_unid,
            event_time,
            region,
            risk_score,
            risk_level,
            magnitude_component,
            depth_component,
            activity_component,
            anomaly_component,
            explanation,
            score_version,
            scored_at
        FROM earthquake_risk_scores
        WHERE event_unid = ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            row = conn.execute(query, [event_unid]).fetchdf()
            if row.empty:
                return None
            return row.to_dict(orient="records")[0]
    except Exception:
        logger.exception("Error executing get_risk_score")
    return None


def list_risk_scores(limit: int = 20) -> List[Dict[str, Any]]:
    """列出最近一批高风险优先排序的评分结果。"""
    query = """
        SELECT
            event_unid,
            event_time,
            region,
            risk_score,
            risk_level,
            magnitude_component,
            depth_component,
            activity_component,
            anomaly_component,
            explanation,
            score_version,
            scored_at
        FROM earthquake_risk_scores
        ORDER BY risk_score DESC, event_time DESC
        LIMIT ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(query, [limit])
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing list_risk_scores")
    return []


def risk_ranking(
    hours: int = config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS,
    limit: int = config.DEFAULT_RISK_QUERY_LIMIT,
    min_risk_level: str = "low",
) -> List[Dict[str, Any]]:
    """查询按风险排序的事件列表。"""
    level_rank_map = {"low": 1, "medium": 2, "high": 3}
    normalized_level = str(min_risk_level or "low").lower()
    minimum_rank = level_rank_map.get(normalized_level, 1)

    query = """
        SELECT
            r.event_unid,
            r.event_time,
            r.region,
            e.latitude,
            e.longitude,
            e.depth,
            e.magnitude,
            e.source,
            e.source_event_id,
            e.is_realtime,
            r.risk_score,
            r.risk_level,
            r.magnitude_component,
            r.depth_component,
            r.activity_component,
            r.anomaly_component,
            r.explanation,
            r.score_version,
            r.scored_at
        FROM earthquake_risk_scores r
        JOIN earthquakes e ON e.unid = r.event_unid
        WHERE
            CAST(r.event_time AS TIMESTAMP) >= now() - (? * INTERVAL '1 hour')
            AND CASE r.risk_level
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                ELSE 1
            END >= ?
        ORDER BY r.risk_score DESC, CAST(r.event_time AS TIMESTAMP) DESC
        LIMIT ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            result = conn.execute(query, [hours, minimum_rank, limit])
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing risk_ranking")
    return []


def risk_event_detail(event_unid: str) -> Optional[Dict[str, Any]]:
    """查询单个事件的基础信息、特征和风险评分详情。"""
    query = """
        SELECT
            e.unid AS event_unid,
            CAST(e.time AS TIMESTAMP) AS event_time,
            COALESCE(NULLIF(e.region, ''), 'UNKNOWN') AS region,
            e.latitude,
            e.longitude,
            e.depth,
            e.magnitude,
            e.source,
            e.source_event_id,
            e.is_realtime,
            e.ingest_time,
            f.recent_window_hours,
            f.recent_region_event_count,
            f.recent_region_avg_magnitude,
            f.historical_baseline_years,
            f.historical_region_event_count,
            f.historical_avg_daily_count,
            f.historical_daily_count_stddev,
            f.anomaly_score,
            f.feature_version,
            f.refreshed_at,
            r.risk_score,
            r.risk_level,
            r.magnitude_component,
            r.depth_component,
            r.activity_component,
            r.anomaly_component,
            r.explanation,
            r.score_version,
            r.scored_at
        FROM earthquakes e
        LEFT JOIN earthquake_features f ON f.event_unid = e.unid
        LEFT JOIN earthquake_risk_scores r ON r.event_unid = e.unid
        WHERE e.unid = ?
    """
    try:
        with _connection_scope(read_only=True) as conn:
            row = conn.execute(query, [event_unid]).fetchdf()
            if row.empty:
                return None
            return row.to_dict(orient="records")[0]
    except Exception:
        logger.exception("Error executing risk_event_detail")
    return None

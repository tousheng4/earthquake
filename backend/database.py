import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import duckdb

DB_PATH = Path(__file__).resolve().with_name("earthquakes.duckdb")
DEFAULT_EXTENSIONS: Set[str] = {"spatial"}
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
        self._params = [lon, lat] + self._params
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
    hours: int = 24 * 30,
) -> List[Dict[str, Any]]:
    """最近邻查询，按距离排序返回指定数量。"""
    return EarthquakeQuery().since(hours).nearest(lon, lat, limit).execute()


def buffered_events(radius_km: float, hours: int = 48) -> List[Dict[str, Any]]:
    """返回按时间筛选后的地震，并给出缓冲区几何的 GeoJSON。"""
    radius_m = radius_km * 1000
    try:
        with _connection_scope(read_only=True) as conn:
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
                [radius_m, _cutoff_iso(hours)],
            )
            return result.df().to_dict(orient="records")
    except Exception:
        logger.exception("Error executing buffered_events query")
        return []


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

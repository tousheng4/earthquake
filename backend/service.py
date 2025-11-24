"""业务逻辑层：封装查询组合与 GeoJSON 构建。"""

from typing import Dict, List, Optional

import database


def recent_events(hours: int) -> List[Dict]:
    """获取最近 N 小时的原始列表数据。"""
    return database.get_recent_earthquakes(hours=hours)


def events(
    hours: int,
    lon: Optional[float] = None,
    lat: Optional[float] = None,
    radius_km: Optional[float] = None,
    min_lon: Optional[float] = None,
    min_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
) -> Dict:
    """根据圆或矩形条件返回 GeoJSON。"""
    query = database.EarthquakeQuery().since(hours)
    
    if lon is not None and lat is not None and radius_km is not None:
        query = query.within_radius(lon, lat, radius_km)
    elif None not in (min_lon, min_lat, max_lon, max_lat):
        query = query.in_bbox(min_lon, min_lat, max_lon, max_lat)
    
    return query.to_geojson()


def nearby(lon: float, lat: float, radius_km: float, hours: int) -> Dict:
    """圆形范围查询并返回 GeoJSON。"""
    return database.EarthquakeQuery().since(hours).within_radius(lon, lat, radius_km).to_geojson()


def buffered(radius_km: float, hours: int) -> Dict:
    """缓冲区查询结果转为 GeoJSON。"""
    rows = database.buffered_events(radius_km=radius_km, hours=hours)
    # buffered_events 返回带 buffer_geojson 字段的特殊格式，需要特殊处理
    features = []
    for row in rows:
        if row.get("buffer_geojson"):
            try:
                geometry = database.json.loads(row["buffer_geojson"])
                properties = {k: v for k, v in row.items() if k != "buffer_geojson"}
                features.append({"type": "Feature", "geometry": geometry, "properties": properties})
            except Exception:
                pass
    return {"type": "FeatureCollection", "features": features}


def overlay(geom_text: str, hours: int) -> Dict:
    """叠加分析结果转为 GeoJSON。"""
    return database.EarthquakeQuery().since(hours).intersects(geom_text).to_geojson()


def nearest_events(lon: float, lat: float, limit: int, hours: int) -> List[Dict]:
    """最近邻原始数据列表。"""
    return database.query_nearest(lon=lon, lat=lat, limit=limit, hours=hours)


def cluster_stats(cell_km: float, hours: int) -> List[Dict]:
    """简单网格聚类统计。"""
    return database.cluster_grid(cell_km=cell_km, hours=hours)


def timeline(start_iso: str | None, end_iso: str | None, limit: int) -> Dict:
    """时间范围结果转为 GeoJSON。"""
    return database.EarthquakeQuery().time_range(start_iso, end_iso).order_by("time ASC").limit(limit).to_geojson()

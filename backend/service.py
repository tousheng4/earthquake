"""业务逻辑层：封装查询组合与结果输出。"""

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
    """根据圆形或矩形条件返回 GeoJSON。"""
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


def region_statistics(
    min_lon: float | None = None,
    min_lat: float | None = None,
    max_lon: float | None = None,
    max_lat: float | None = None,
    lon: float | None = None,
    lat: float | None = None,
    radius_km: float | None = None,
    hours: int = 48,
) -> Dict:
    """区域统计。"""
    return database.region_statistics(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        lon=lon,
        lat=lat,
        radius_km=radius_km,
        hours=hours,
    )


def magnitude_distribution(
    min_lon: float | None = None,
    min_lat: float | None = None,
    max_lon: float | None = None,
    max_lat: float | None = None,
    hours: int = 48,
) -> List[Dict]:
    """震级分布统计。"""
    return database.magnitude_distribution(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        hours=hours,
    )


def hourly_distribution(hours: int = 48) -> List[Dict]:
    """按小时统计地震频次。"""
    return database.hourly_distribution(hours=hours)


def history_timeline(years: int, bucket: str = "month") -> List[Dict]:
    """历史时间分布统计。"""
    return database.history_timeline(years=years, bucket=bucket)


def history_region_distribution(years: int, limit: int = 20) -> List[Dict]:
    """历史区域分布统计。"""
    return database.history_region_distribution(years=years, limit=limit)

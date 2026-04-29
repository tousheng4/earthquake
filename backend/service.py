"""业务逻辑层：封装查询组合与结果输出。"""

from typing import Dict, List, Optional

import config
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


def buffered(radius_km: float, hours: int, event_unid: str | None = None) -> Dict:
    """缓冲区查询结果转为 GeoJSON。"""
    rows = database.buffered_events(radius_km=radius_km, hours=hours, event_unid=event_unid)
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


def risk_ranking(
    hours: int = config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS,
    limit: int = config.DEFAULT_RISK_QUERY_LIMIT,
    min_risk_level: str = "low",
) -> List[Dict]:
    """高风险事件排行。"""
    return database.risk_ranking(hours=hours, limit=limit, min_risk_level=min_risk_level)


def risk_event_detail(event_unid: str) -> Dict | None:
    """单事件风险评估详情。"""
    row = database.risk_event_detail(event_unid)
    if row is None:
        return None

    return {
        "event": {
            "event_unid": row.get("event_unid"),
            "event_time": row.get("event_time"),
            "region": row.get("region"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "depth": row.get("depth"),
            "magnitude": row.get("magnitude"),
            "source": row.get("source"),
            "source_event_id": row.get("source_event_id"),
            "is_realtime": row.get("is_realtime"),
            "ingest_time": row.get("ingest_time"),
        },
        "feature_summary": {
            "recent_window_hours": row.get("recent_window_hours"),
            "recent_region_event_count": row.get("recent_region_event_count"),
            "recent_region_avg_magnitude": row.get("recent_region_avg_magnitude"),
            "historical_baseline_years": row.get("historical_baseline_years"),
            "historical_region_event_count": row.get("historical_region_event_count"),
            "historical_avg_daily_count": row.get("historical_avg_daily_count"),
            "historical_daily_count_stddev": row.get("historical_daily_count_stddev"),
            "anomaly_score": row.get("anomaly_score"),
            "feature_version": row.get("feature_version"),
            "refreshed_at": row.get("refreshed_at"),
        },
        "risk": {
            "risk_score": row.get("risk_score"),
            "risk_level": row.get("risk_level"),
            "magnitude_component": row.get("magnitude_component"),
            "depth_component": row.get("depth_component"),
            "activity_component": row.get("activity_component"),
            "anomaly_component": row.get("anomaly_component"),
            "explanation": row.get("explanation"),
            "score_version": row.get("score_version"),
            "scored_at": row.get("scored_at"),
        },
    }

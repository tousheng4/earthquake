"""Flask API：提供地震查询与 GeoJSON 输出。"""
from flask import Flask, jsonify, request
from flask_cors import CORS

import config
import service

app = Flask(__name__)
CORS(app)


@app.route("/earthquakes")
def earthquakes_api():
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    data = service.recent_events(hours=hours)
    return jsonify(data)


@app.route("/earthquakes.geojson")
def earthquakes_geojson():
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    lon = request.args.get("lon", type=float)
    lat = request.args.get("lat", type=float)
    radius_km = request.args.get("radius_km", type=float)
    min_lon = request.args.get("min_lon", type=float)
    min_lat = request.args.get("min_lat", type=float)
    max_lon = request.args.get("max_lon", type=float)
    max_lat = request.args.get("max_lat", type=float)

    geojson = service.events(
        hours=hours,
        lon=lon,
        lat=lat,
        radius_km=radius_km,
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
    )
    return jsonify(geojson)


@app.route("/earthquakes/near")
def earthquakes_near():
    lon = request.args.get("lon", type=float)
    lat = request.args.get("lat", type=float)
    radius_km = request.args.get("radius_km", type=float)
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    if lon is None or lat is None or radius_km is None:
        return jsonify({"error": "lon, lat, radius_km are required"}), 400
    geojson = service.nearby(lon, lat, radius_km, hours=hours)
    return jsonify(geojson)


@app.route("/earthquakes/buffer")
def earthquakes_buffer():
    radius_km = request.args.get("radius_km", type=float)
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    if radius_km is None:
        return jsonify({"error": "radius_km is required"}), 400
    geojson = service.buffered(radius_km=radius_km, hours=hours)
    return jsonify(geojson)


@app.route("/earthquakes/overlay")
def earthquakes_overlay():
    geom_text = request.args.get("geom")
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    if not geom_text:
        return jsonify({"error": "geom (WKT or GeoJSON) is required"}), 400
    geojson = service.overlay(geom_text=geom_text, hours=hours)
    return jsonify(geojson)


@app.route("/earthquakes/nearest")
def earthquakes_nearest():
    lon = request.args.get("lon", type=float)
    lat = request.args.get("lat", type=float)
    limit = request.args.get("limit", default=10, type=int)
    hours = request.args.get("hours", default=config.DEFAULT_NEAREST_LOOKBACK_HOURS, type=int)

    if lon is None or lat is None:
        return jsonify({"error": "lon and lat are required"}), 400

    rows = service.nearest_events(lon=lon, lat=lat, limit=limit, hours=hours)
    return jsonify(rows)


@app.route("/stats/cluster")
def stats_cluster():
    cell_km = request.args.get("cell_km", default=config.DEFAULT_CLUSTER_CELL_KM, type=float)
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    rows = service.cluster_stats(cell_km=cell_km, hours=hours)
    return jsonify(rows)


@app.route("/stats/region")
def stats_region():
    """区域统计：返回地震频次、平均震级、最高震级等"""
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    lon = request.args.get("lon", type=float)
    lat = request.args.get("lat", type=float)
    radius_km = request.args.get("radius_km", type=float)
    min_lon = request.args.get("min_lon", type=float)
    min_lat = request.args.get("min_lat", type=float)
    max_lon = request.args.get("max_lon", type=float)
    max_lat = request.args.get("max_lat", type=float)

    stats = service.region_statistics(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        lon=lon,
        lat=lat,
        radius_km=radius_km,
        hours=hours,
    )
    return jsonify(stats)


@app.route("/stats/magnitude-distribution")
def stats_magnitude_distribution():
    """震级分布统计（用于柱状图）"""
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    min_lon = request.args.get("min_lon", type=float)
    min_lat = request.args.get("min_lat", type=float)
    max_lon = request.args.get("max_lon", type=float)
    max_lat = request.args.get("max_lat", type=float)

    distribution = service.magnitude_distribution(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        hours=hours,
    )
    return jsonify(distribution)


@app.route("/stats/hourly-distribution")
def stats_hourly_distribution():
    """按小时统计地震频次（用于24小时折线图）"""
    hours = request.args.get("hours", default=config.DEFAULT_QUERY_HOURS, type=int)
    distribution = service.hourly_distribution(hours=hours)
    return jsonify(distribution)


@app.route("/stats/history/timeline")
def stats_history_timeline():
    years = request.args.get("years", default=config.DEFAULT_HISTORY_IMPORT_YEARS, type=int)
    bucket = request.args.get("bucket", default="month", type=str)
    rows = service.history_timeline(years=years, bucket=bucket)
    return jsonify(rows)


@app.route("/stats/history/region_dist")
def stats_history_region_distribution():
    years = request.args.get("years", default=config.DEFAULT_HISTORY_IMPORT_YEARS, type=int)
    limit = request.args.get("limit", default=20, type=int)
    rows = service.history_region_distribution(years=years, limit=limit)
    return jsonify(rows)


@app.route("/risk/ranking")
def risk_ranking():
    hours = request.args.get("hours", default=config.DEFAULT_FEATURE_RECENT_WINDOW_HOURS, type=int)
    limit = request.args.get("limit", default=config.DEFAULT_RISK_QUERY_LIMIT, type=int)
    min_risk_level = request.args.get("min_risk_level", default="low", type=str)
    rows = service.risk_ranking(hours=hours, limit=limit, min_risk_level=min_risk_level)
    return jsonify(rows)


@app.route("/risk/events/<event_unid>")
def risk_event_detail_api(event_unid: str):
    detail = service.risk_event_detail(event_unid)
    if detail is None:
        return jsonify({"error": "event not found"}), 404
    return jsonify(detail)


@app.route("/earthquakes/timeline")
def earthquakes_timeline():
    start_time = request.args.get("start")
    end_time = request.args.get("end")
    limit = request.args.get("limit", default=config.DEFAULT_TIMELINE_LIMIT, type=int)
    geojson = service.timeline(start_iso=start_time, end_iso=end_time, limit=limit)
    return jsonify(geojson)


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000, debug=True)

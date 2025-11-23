"""Flask API：提供地震查询与 GeoJSON 输出。"""

from __future__ import annotations

import json
from typing import Dict, List

from flask import Flask, jsonify, request
from flask_cors import CORS

import database

app = Flask(__name__)
CORS(app)


def _parse_int(arg: str | None, default: int) -> int:
    try:
        return int(arg) if arg is not None else default
    except ValueError:
        return default


def _parse_float(arg: str | None) -> float | None:
    try:
        return float(arg) if arg is not None else None
    except ValueError:
        return None


def _to_feature_collection(rows: List[Dict], geom_field: str | None = None) -> Dict:
    """将查询结果转换为 GeoJSON FeatureCollection。"""
    features = []
    for row in rows:
        if geom_field and row.get(geom_field):
            try:
                geometry = json.loads(row[geom_field])
            except Exception:
                continue
        else:
            lon = row.get("longitude")
            lat = row.get("latitude")
            if lon is None or lat is None:
                continue
            geometry = {"type": "Point", "coordinates": [lon, lat]}

        properties = {k: v for k, v in row.items() if k not in {"geom", geom_field}}
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})
    return {"type": "FeatureCollection", "features": features}


@app.route("/earthquakes")
def earthquakes_api():
    hours = _parse_int(request.args.get("hours"), 48)
    data = database.get_recent_earthquakes(hours=hours)
    return jsonify(data)


@app.route("/earthquakes.geojson")
def earthquakes_geojson():
    hours = _parse_int(request.args.get("hours"), 48)
    lon = _parse_float(request.args.get("lon"))
    lat = _parse_float(request.args.get("lat"))
    radius_km = _parse_float(request.args.get("radius_km"))
    min_lon = _parse_float(request.args.get("min_lon"))
    min_lat = _parse_float(request.args.get("min_lat"))
    max_lon = _parse_float(request.args.get("max_lon"))
    max_lat = _parse_float(request.args.get("max_lat"))

    rows: List[Dict]
    if lon is not None and lat is not None and radius_km is not None:
        rows = database.query_within_radius(lon, lat, radius_km, hours=hours)
    elif None not in (min_lon, min_lat, max_lon, max_lat):
        rows = database.query_bbox(min_lon, min_lat, max_lon, max_lat, hours=hours)
    else:
        rows = database.get_recent_earthquakes(hours=hours)

    return jsonify(_to_feature_collection(rows))


@app.route("/earthquakes/near")
def earthquakes_near():
    lon = _parse_float(request.args.get("lon"))
    lat = _parse_float(request.args.get("lat"))
    radius_km = _parse_float(request.args.get("radius_km"))
    hours = _parse_int(request.args.get("hours"), 48)
    if lon is None or lat is None or radius_km is None:
        return jsonify({"error": "lon, lat, radius_km are required"}), 400
    rows = database.query_within_radius(lon, lat, radius_km, hours=hours)
    return jsonify(_to_feature_collection(rows))


@app.route("/earthquakes/buffer")
def earthquakes_buffer():
    radius_km = _parse_float(request.args.get("radius_km"))
    hours = _parse_int(request.args.get("hours"), 48)
    if radius_km is None:
        return jsonify({"error": "radius_km is required"}), 400
    rows = database.buffered_events(radius_km=radius_km, hours=hours)
    return jsonify(_to_feature_collection(rows, geom_field="buffer_geojson"))


@app.route("/earthquakes/overlay")
def earthquakes_overlay():
    geom_text = request.args.get("geom")
    hours = _parse_int(request.args.get("hours"), 48)
    if not geom_text:
        return jsonify({"error": "geom (WKT or GeoJSON) is required"}), 400
    rows = database.query_overlay(geom_text=geom_text, hours=hours)
    return jsonify(_to_feature_collection(rows))


@app.route("/earthquakes/nearest")
def earthquakes_nearest():
    lon = _parse_float(request.args.get("lon"))
    lat = _parse_float(request.args.get("lat"))
    limit = _parse_int(request.args.get("limit"), 10)
    hours = _parse_int(request.args.get("hours"), 24 * 30)

    if lon is None or lat is None:
        return jsonify({"error": "lon and lat are required"}), 400

    rows = database.query_nearest(lon=lon, lat=lat, limit=limit, hours=hours)
    return jsonify(rows)


@app.route("/stats/cluster")
def stats_cluster():
    cell_km = _parse_float(request.args.get("cell_km")) or 50.0
    hours = _parse_int(request.args.get("hours"), 48)
    rows = database.cluster_grid(cell_km=cell_km, hours=hours)
    return jsonify(rows)


@app.route("/earthquakes/timeline")
def earthquakes_timeline():
    start_time = request.args.get("start")
    end_time = request.args.get("end")
    limit = _parse_int(request.args.get("limit"), 2000)
    rows = database.get_time_window(start_iso=start_time, end_iso=end_time, limit=limit)
    return jsonify(_to_feature_collection(rows))


if __name__ == "__main__":
    database.init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

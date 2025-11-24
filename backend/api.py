"""Flask API：提供地震查询与 GeoJSON 输出。"""
from flask import Flask, jsonify, request
from flask_cors import CORS

import service

app = Flask(__name__)
CORS(app)


@app.route("/earthquakes")
def earthquakes_api():
    hours = request.args.get("hours", default=48, type=int)
    data = service.recent_events(hours=hours)
    return jsonify(data)


@app.route("/earthquakes.geojson")
def earthquakes_geojson():
    hours = request.args.get("hours", default=48, type=int)
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
    hours = request.args.get("hours", default=48, type=int)
    if lon is None or lat is None or radius_km is None:
        return jsonify({"error": "lon, lat, radius_km are required"}), 400
    geojson = service.nearby(lon, lat, radius_km, hours=hours)
    return jsonify(geojson)


@app.route("/earthquakes/buffer")
def earthquakes_buffer():
    radius_km = request.args.get("radius_km", type=float)
    hours = request.args.get("hours", default=48, type=int)
    if radius_km is None:
        return jsonify({"error": "radius_km is required"}), 400
    geojson = service.buffered(radius_km=radius_km, hours=hours)
    return jsonify(geojson)


@app.route("/earthquakes/overlay")
def earthquakes_overlay():
    geom_text = request.args.get("geom")
    hours = request.args.get("hours", default=48, type=int)
    if not geom_text:
        return jsonify({"error": "geom (WKT or GeoJSON) is required"}), 400
    geojson = service.overlay(geom_text=geom_text, hours=hours)
    return jsonify(geojson)


@app.route("/earthquakes/nearest")
def earthquakes_nearest():
    lon = request.args.get("lon", type=float)
    lat = request.args.get("lat", type=float)
    limit = request.args.get("limit", default=10, type=int)
    hours = request.args.get("hours", default=24 * 30, type=int)

    if lon is None or lat is None:
        return jsonify({"error": "lon and lat are required"}), 400

    rows = service.nearest_events(lon=lon, lat=lat, limit=limit, hours=hours)
    return jsonify(rows)


@app.route("/stats/cluster")
def stats_cluster():
    cell_km = request.args.get("cell_km", default=50.0, type=float)
    hours = request.args.get("hours", default=48, type=int)
    rows = service.cluster_stats(cell_km=cell_km, hours=hours)
    return jsonify(rows)


@app.route("/earthquakes/timeline")
def earthquakes_timeline():
    start_time = request.args.get("start")
    end_time = request.args.get("end")
    limit = request.args.get("limit", default=2000, type=int)
    geojson = service.timeline(start_iso=start_time, end_iso=end_time, limit=limit)
    return jsonify(geojson)


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000, debug=True)

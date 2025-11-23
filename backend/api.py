"""Flask API：提供 /earthquakes 接口，返回最近 48 小时的地震为 JSON。"""

from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

import database

app = Flask(__name__)
CORS(app)


@app.route("/earthquakes")
def earthquakes_api():
    data = database.get_recent_earthquakes(hours=48)
    return jsonify(data)


if __name__ == "__main__":
    database.init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

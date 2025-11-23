"""
Flask API：提供 /earthquakes 接口，返回最近 48 小时的地震为 JSON。
"""
import json
import os
import csv
from datetime import datetime, timedelta, timezone

from flask import Flask,jsonify
from flask_cors import CORS

app=Flask(__name__)
CORS(app)

CSV_PATH=os.path.join(os.path.dirname(__file__),"earthquakes.csv")

def read_recent_earthquakes(hours=48):
    if not os.path.exists(CSV_PATH):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result=[]

    with open(CSV_PATH,newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        for row in reader:
            time_str=row['time']
            print(time_str)
            try:
                dt=datetime.fromisoformat(time_str.replace("Z","+00:00"))
            except Exception:
                continue

            if dt<cutoff:
                continue

            quake={
                "time":time_str,
                "latitude":float(row["latitude"]),
                "longitude":float(row["longitude"]),
                "magnitude":float(row["magnitude"]),
                "region":row["region"],
                "unid":row["unid"],
            }
            result.append(quake)

    result.sort(key=lambda x: x["time"],reverse=True)
    print(result)
    return result

@app.route("/earthquakes")
def earthquakes_api():
    data=read_recent_earthquakes(hours=48)
    return jsonify(data)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)

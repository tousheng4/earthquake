# -*- coding: utf-8 -*-
"""
监听 EMSC 的地震 WebSocket，把数据实时写入 CSV 文件。
"""

import os
import csv
import json
import logging
import sys
from datetime import datetime

from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado import gen

# WebSocket 地址（EMSC 的实时地震流）
WS_URL = "wss://www.seismicportal.eu/standing_order/websocket"

# 心跳间隔，避免连接闲置被服务器断开
PING_INTERVAL = 15

# CSV 文件路径：位于当前 backend 目录下
CSV_PATH = os.path.join(os.path.dirname(__file__), "earthquakes.csv")

# CSV 表头
CSV_FIELDS = ["time", "latitude", "longitude", "magnitude", "region", "unid"]

# 已写入的事件 ID，用来去重
seen_unids = set()


def ensure_csv():
    """
    如果 CSV 不存在，就创建并写入表头。
    """
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_FIELDS)
        logging.info("Created CSV file: %s", CSV_PATH)
    else:
        logging.info("Using existing CSV file: %s", CSV_PATH)


def process_message(raw_message: str):
    """
    解析一条 WebSocket 消息，并把有效事件写入 CSV。
    """
    try:
        data = json.loads(raw_message)
    except json.JSONDecodeError:
        logging.warning("Not JSON, skipped: %r", raw_message)
        return

    event = data.get("data", {})
    props = event.get("properties", {})
    geom = event.get("geometry", {})

    event_time = props.get("time", "")
    magnitude = props.get("mag", None)
    region = props.get("flynn_region", "")
    unid = props.get("unid", None)

    coords = geom.get("coordinates", [None, None])
    longitude = coords[0]
    latitude = coords[1]

    # 字段不完整就丢弃
    if None in (unid, longitude, latitude, magnitude) or not event_time:
        logging.warning("Incomplete event, skipped.")
        return

    # region 里如果有逗号会影响 CSV，替换为空格
    region = region.replace(",", " ")

    # 标准化时间字符串为 ISO8601
    try:
        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
        event_time_str = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        event_time_str = event_time

    # 去重，同一个 unid 只写一次
    if unid in seen_unids:
        logging.debug("Duplicate event %s skipped", unid)
        return
    seen_unids.add(unid)

    row = [
        event_time_str,
        f"{latitude:.4f}",
        f"{longitude:.4f}",
        f"{float(magnitude):.1f}",
        region,
        unid,
    ]

    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
        logging.info("New EQ: M%.1f %s (%.4f, %.4f)",
                     float(magnitude), region, latitude, longitude)
    except Exception:
        logging.exception("Failed to write to CSV")


@gen.coroutine
def listen(ws):
    """
    持续从 WebSocket 读取消息。
    """
    while True:
        msg = yield ws.read_message()
        if msg is None:
            logging.warning("WebSocket closed by server.")
            break
        process_message(msg)


@gen.coroutine
def launch_client():
    """
    建立 WebSocket 连接并开始监听。
    """
    try:
        logging.info("Connecting to %s", WS_URL)
        ws = yield websocket_connect(WS_URL, ping_interval=PING_INTERVAL)
    except Exception:
        logging.exception("Connection error")
    else:
        logging.info("Connected, start listening...")
        yield listen(ws)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    ensure_csv()

    loop = IOLoop.instance()
    launch_client()  # 把协程注册到事件循环

    try:
        logging.info("Starting IOLoop, Ctrl+C to stop.")
        loop.start()
    except KeyboardInterrupt:
        logging.info("Stopping...")
        loop.stop()

# -*- coding: utf-8 -*-
"""监听 EMSC 的地震 WebSocket，把数据实时写入 DuckDB。"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from tornado import gen, websocket
from tornado.ioloop import IOLoop

import database

WS_URL = "wss://www.seismicportal.eu/standing_order/websocket"
PING_INTERVAL = 15

logger = logging.getLogger(__name__)


def process_message(raw_message: str) -> None:
    """解析一条 WebSocket 消息，并把有效事件写入数据库。"""
    try:
        data: Dict[str, Any] = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning("Not JSON, skipped: %r", raw_message)
        return

    event = data.get("data", {})
    props = event.get("properties", {})
    geometry = event.get("geometry", {})

    event_time = props.get("time", "")
    magnitude = props.get("mag")
    region = props.get("flynn_region", "")
    unid = props.get("unid")
    depth = props.get("depth")
    
    coordinates = geometry.get("coordinates", [None, None])
    longitude, latitude = coordinates[0], coordinates[1]

    if None in (unid, longitude, latitude, magnitude) or not event_time:
        logger.warning("Incomplete event, skipped.")
        return

    region = region.replace(",", " ")

    try:
        event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        pass

    quake_data = {
        "unid": unid,
        "time": event_time,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "magnitude": float(magnitude),
        "region": region,
        "depth": float(depth) if depth is not None else None,
    }

    if database.insert_earthquake(quake_data):
        logger.info(
            "New EQ: M%.1f %s (%.4f, %.4f)",
            float(magnitude),
            region,
            float(latitude),
            float(longitude),
        )


@gen.coroutine
def listen(ws: websocket.WebSocketClientConnection):
    """持续从 WebSocket 读取消息。"""
    while True:
        msg = yield ws.read_message()
        if msg is None:
            logger.warning("WebSocket closed by server.")
            break
        process_message(msg)


@gen.coroutine
def launch_client():
    """建立 WebSocket 连接并开始监听。"""
    try:
        logger.info("Connecting to %s", WS_URL)
        ws = yield websocket.websocket_connect(WS_URL, ping_interval=PING_INTERVAL)
    except Exception:
        logger.exception("Connection error")
    else:
        logger.info("Connected, start listening...")
        yield listen(ws)


def start_listener_loop():
    """在当前线程启动 IOLoop 并监听 WebSocket。"""
    loop = IOLoop.instance()
    loop.spawn_callback(launch_client)
    logger.info("Starting listener IOLoop...")
    try:
        loop.start()
    except KeyboardInterrupt:
        logger.info("Stopping listener loop...")
        loop.stop()


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    start_listener_loop()

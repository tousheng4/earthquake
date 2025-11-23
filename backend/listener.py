# -*- coding: utf-8 -*-
"""监听 EMSC 的地震 WebSocket，把数据实时写入 DuckDB。"""

from __future__ import annotations

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

seen_unids: set[str] = set()
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
    geom = event.get("geometry", {})

    event_time = props.get("time", "")
    magnitude = props.get("mag")
    region = props.get("flynn_region", "")
    unid = props.get("unid")
    depth = props.get("depth")

    coords = geom.get("coordinates", [None, None])
    longitude, latitude = coords[0], coords[1]

    if None in (unid, longitude, latitude, magnitude) or not event_time:
        logger.warning("Incomplete event, skipped.")
        return

    region = region.replace(",", " ")

    try:
        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
        event_time_str = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        event_time_str = event_time

    if unid in seen_unids:
        logger.debug("Duplicate event %s skipped", unid)
        return

    quake_data = {
        "unid": unid,
        "time": event_time_str,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "magnitude": float(magnitude),
        "region": region,
        "depth": float(depth) if depth is not None else None,
    }

    if database.insert_earthquake(quake_data):
        seen_unids.add(unid)
        logger.info(
            "New EQ: M%.1f %s (%.4f, %.4f)",
            float(magnitude),
            region,
            float(latitude),
            float(longitude),
        )
    else:
        seen_unids.add(unid)


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


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    database.init_db()
    seen_unids = database.get_all_unids()
    logger.info("Loaded %d existing events from DB.", len(seen_unids))

    loop = IOLoop.instance()
    launch_client()

    try:
        logger.info("Starting IOLoop, Ctrl+C to stop.")
        loop.start()
    except KeyboardInterrupt:
        logger.info("Stopping...")
        loop.stop()

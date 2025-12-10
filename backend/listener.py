# -*- coding: utf-8 -*-
"""监听 EMSC 的地震 WebSocket，把数据实时写入 DuckDB。"""

import json
import logging
import signal
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from tornado import gen, websocket
from tornado.ioloop import IOLoop, PeriodicCallback

import database

WS_URL = "wss://www.seismicportal.eu/standing_order/websocket"
PING_INTERVAL = 15
RECONNECT_DELAY = 5  # 断线重连延迟（秒）
RESTART_INTERVAL = 3600  # 定时重启间隔（秒），0 表示不重启

logger = logging.getLogger(__name__)

# 当前连接实例
_current_ws: Optional[websocket.WebSocketClientConnection] = None


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
    try:
        while True:
            msg = yield ws.read_message()
            if msg is None:
                logger.warning("WebSocket closed by server.")
                break
            process_message(msg)
    except Exception as e:
        logger.info("Listen loop interrupted: %s", e)


@gen.coroutine
def launch_client():
    """建立 WebSocket 连接并开始监听，断线自动重连。"""
    global _current_ws

    while True:
        try:
            logger.info("Connecting to %s", WS_URL)
            _current_ws = yield websocket.websocket_connect(
                WS_URL, ping_interval=PING_INTERVAL
            )
            logger.info("Connected, start listening...")
            yield listen(_current_ws)
        except Exception as e:
            # 如果是主动关闭，不再重连
            if "closed" in str(e).lower() or not IOLoop.current().is_running():
                logger.info("Connection closed, exiting...")
                break
            logger.exception("Connection error")
        finally:
            _current_ws = None

        # 检查事件循环是否还在运行
        if not IOLoop.current().is_running():
            break
            
        logger.info("Will reconnect in %d seconds...", RECONNECT_DELAY)
        yield gen.sleep(RECONNECT_DELAY)


def restart_connection():
    """主动关闭当前连接，触发重连。"""
    global _current_ws
    if _current_ws is not None:
        logger.info("Scheduled restart, closing connection...")
        _current_ws.close()


def start_listener_loop():
    """在当前线程启动 IOLoop 并监听 WebSocket（独立运行模式）。"""
    loop = IOLoop.instance()
    loop.spawn_callback(launch_client)

    # 定时重启
    if RESTART_INTERVAL > 0:
        pc = PeriodicCallback(restart_connection, RESTART_INTERVAL * 1000)
        pc.start()
        logger.info("Scheduled restart every %d seconds", RESTART_INTERVAL)

    logger.info("Starting listener IOLoop...")
    
    def shutdown_handler(sig, frame):
        global _current_ws
        logger.info("Stopping listener loop...")
        if _current_ws is not None:
            _current_ws.close()
        loop.stop()
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        loop.start()
    finally:
        if _current_ws is not None:
            _current_ws.close()
        logger.info("Listener stopped")


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    start_listener_loop()

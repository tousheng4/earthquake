"""统一入口：Tornado IOLoop 同时运行 Flask API 与 WebSocket 监听器。"""

import logging
import signal
import sys

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.wsgi import WSGIContainer

import api
import database
import listener


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # listener 日志写入文件
    log = logging.getLogger("listener")
    log.handlers.clear()
    log.addHandler(logging.FileHandler("listener.log"))
    log.setLevel(logging.INFO)
    log.propagate = False

    loop = IOLoop.current()

    # Flask 通过 WSGIContainer 嵌入 Tornado
    http_server = HTTPServer(WSGIContainer(api.app))
    http_server.listen(5000, address="0.0.0.0")
    logging.info("Flask API 已启动: http://0.0.0.0:5000")

    # WebSocket 监听器
    loop.spawn_callback(listener.launch_client)
    if listener.RESTART_INTERVAL > 0:
        PeriodicCallback(listener.restart_connection, listener.RESTART_INTERVAL * 1000).start()
        logging.info("WebSocket 监听器已启动 (每 %d 秒重启)", listener.RESTART_INTERVAL)
    else:
        logging.info("WebSocket 监听器已启动")

    # 优雅停止
    def shutdown(sig, frame):
        logging.info("收到停止信号，正在关闭...")
        
        def cleanup():
            # 关闭 WebSocket 连接
            if listener._current_ws is not None:
                listener._current_ws.close()
            
            # 关闭数据库连接池
            if database._connection_pool is not None:
                database._connection_pool.close()
            
            # 停止 HTTP 服务器
            http_server.stop()
            
            # 停止事件循环
            loop.stop()
            
            logging.info("所有资源已清理")
        
        loop.add_callback(cleanup)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.start()
    finally:
        # 确保退出时清理资源
        if listener._current_ws is not None:
            listener._current_ws.close()
        if database._connection_pool is not None:
            database._connection_pool.close()
        logging.info("服务已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()

"""统一入口：使用线程池同时启动 API 与监听器。"""

import logging
from concurrent.futures import ThreadPoolExecutor

import api
import listener


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # 将 listener 日志写入文件，不向终端冒泡
    logger = logging.getLogger("listener")
    logger.handlers.clear()
    handler = logging.FileHandler("listener.log")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    with ThreadPoolExecutor(max_workers=2) as ex:
        # 监听器线程
        ex.submit(listener.start_listener_loop)

        # Flask API 线程（关闭重载避免多进程）
        ex.submit(
            api.app.run,
            host="0.0.0.0",
            port=5000,
            debug=False,
            use_reloader=False,
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""初始化 DuckDB 数据库：安装扩展并创建表结构。"""

import logging
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().with_name("earthquakes.duckdb")
EXTENSIONS = ["spatial"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def install_extensions(conn: duckdb.DuckDBPyConnection) -> None:
    """安装并加载 DuckDB 扩展。"""
    for ext in EXTENSIONS:
        logger.info("安装扩展: %s", ext)
        conn.execute(f"INSTALL {ext}")
        logger.info("加载扩展: %s", ext)
        conn.execute(f"LOAD {ext}")
        logger.info("✓ 扩展 %s 已就绪", ext)


def create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """创建表结构（如果不存在）。"""
    logger.info("创建表结构...")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS earthquakes (
            unid VARCHAR PRIMARY KEY,
            time TIMESTAMP NOT NULL,
            latitude DOUBLE NOT NULL,
            longitude DOUBLE NOT NULL,
            depth DOUBLE,
            magnitude DOUBLE NOT NULL,
            region VARCHAR,
            geom GEOMETRY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建索引
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_earthquakes_time 
        ON earthquakes(time DESC)
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_earthquakes_magnitude 
        ON earthquakes(magnitude DESC)
    """)
    
    logger.info("✓ 表结构已创建")


def optimize_settings(conn: duckdb.DuckDBPyConnection) -> None:
    """优化数据库设置。"""
    logger.info("优化数据库设置...")
    
    # 设置内存限制（根据需要调整）
    conn.execute("SET memory_limit='2GB'")
    
    # 设置线程数
    conn.execute("SET threads=4")
    
    # 启用进度条（仅交互式）
    # conn.execute("SET enable_progress_bar=true")
    
    logger.info("✓ 数据库设置已优化")


def show_info(conn: duckdb.DuckDBPyConnection) -> None:
    """显示数据库信息。"""
    logger.info("数据库信息:")
    logger.info("  路径: %s", DB_PATH)
    logger.info("  大小: %.2f MB", DB_PATH.stat().st_size / 1024 / 1024)
    
    # 显示已加载的扩展
    result = conn.execute("SELECT * FROM duckdb_extensions() WHERE loaded = true").fetchall()
    logger.info("  已加载扩展: %s", ", ".join(row[0] for row in result))
    
    # 显示表信息
    result = conn.execute("SELECT COUNT(*) FROM earthquakes").fetchone()
    logger.info("  地震记录数: %d", result[0])


def main() -> None:
    logger.info("开始初始化数据库...")
    
    # 连接数据库
    conn = duckdb.connect(str(DB_PATH))
    
    try:
        # 1. 安装扩展
        install_extensions(conn)
        
        # 2. 创建表结构
        create_tables(conn)
        
        # 3. 优化设置
        optimize_settings(conn)
        
        # 4. 显示信息
        show_info(conn)
        
        logger.info("✓ 数据库初始化完成")
        
    except Exception as e:
        logger.exception("初始化失败: %s", e)
        return 1
    finally:
        conn.close()
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


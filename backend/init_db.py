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


def create_tables(conn: duckdb.DuckDBPyConnection, schema: str = "") -> None:
    """创建表结构（如果不存在）。"""
    logger.info("创建表结构...")
    
    table_name = f"{schema}.earthquakes" if schema else "earthquakes"
    
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
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
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_earthquakes_time 
        ON {table_name}(time DESC)
    """)
    
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_earthquakes_magnitude 
        ON {table_name}(magnitude DESC)
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


def show_info(conn: duckdb.DuckDBPyConnection, schema: str = "") -> None:
    """显示数据库信息。"""
    logger.info("数据库信息:")
    logger.info("  路径: %s", DB_PATH)
    if DB_PATH.exists():
        logger.info("  大小: %.2f MB", DB_PATH.stat().st_size / 1024 / 1024)
    
    # 显示已加载的扩展
    result = conn.execute("SELECT * FROM duckdb_extensions() WHERE loaded = true").fetchall()
    logger.info("  已加载扩展: %s", ", ".join(row[0] for row in result))
    
    # 显示表信息
    table_name = f"{schema}.earthquakes" if schema else "earthquakes"
    try:
        result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        logger.info("  地震记录数: %d", result[0])
    except Exception:
        logger.info("  地震记录数: 0 (表不存在)")


def main() -> None:
    logger.info("开始初始化数据库...")
    
    # 先确保扩展已安装（全局安装）
    logger.info("安装扩展...")
    temp_conn = duckdb.connect(":memory:")
    for ext in EXTENSIONS:
        try:
            temp_conn.execute(f"INSTALL {ext}")
            logger.info("✓ 扩展 %s 已安装", ext)
        except Exception as e:
            logger.warning("扩展 %s 可能已安装: %s", ext, e)
    temp_conn.close()
    
    # 连接数据库，使用配置确保扩展在连接时加载
    logger.info("连接数据库...")
    conn = None
    use_attach = False
    
    try:
        # 尝试直接连接（如果数据库不存在或没有使用扩展索引）
        conn = duckdb.connect(str(DB_PATH))
        # 立即加载扩展
        for ext in EXTENSIONS:
            conn.execute(f"LOAD {ext}")
            logger.info("✓ 扩展 %s 已加载", ext)
    except Exception as e:
        if "RTREE" in str(e) or "extension" in str(e).lower():
            # 如果是因为扩展未加载，先连接内存数据库加载扩展，再附加
            logger.info("检测到需要扩展，使用 ATTACH 方式...")
            conn = duckdb.connect(":memory:")
            for ext in EXTENSIONS:
                conn.execute(f"LOAD {ext}")
            conn.execute(f"ATTACH '{DB_PATH}' AS db")
            use_attach = True
        else:
            raise
    
    try:
        schema = "db" if use_attach else ""
        
        # 1. 创建表结构
        create_tables(conn, schema)
        
        # 2. 优化设置
        optimize_settings(conn)
        
        # 3. 显示信息
        show_info(conn, schema)
        
        logger.info("✓ 数据库初始化完成")
        
    except Exception as e:
        logger.exception("初始化失败: %s", e)
        return 1
    finally:
        if conn:
            conn.close()
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


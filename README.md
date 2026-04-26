# 全球地震实时监测与可视化分析平台

A full-stack real-time earthquake monitoring and visualization platform.

## 项目概述

本项目是一个地震实时监测与可视化分析平台，后端采用 Python（Flask + Tornado）提供 RESTful API 和 WebSocket 实时数据采集，前端采用 Vue 3 构建交互式可视化界面。数据通过 DuckDB 存储并支持空间查询。

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                          │
│  ECharts 地图 + Element Plus UI + Axios                  │
│  运行在 http://localhost:5173                           │
└─────────────────┬───────────────────────────────────────┘
                  │ (Vite 代理 /api → :5000)
┌─────────────────▼───────────────────────────────────────┐
│              后端 (Flask + Tornado)                     │
│  Flask: REST API (20+ 端点)                             │
│  Tornado: WebSocket 实时采集 + IOLoop                   │
│  端口: 5000                                             │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│              数据层 (DuckDB + spatial)                  │
│  earthquakes / earthquake_features / earthquake_risk_scores │
└─────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| **Python 3.11+** | 运行环境 |
| **Flask 3.1.2** | REST API 框架 |
| **Tornado 6.5.2** | WebSocket 客户端 + IOLoop 事件循环 |
| **DuckDB 1.4.2** + spatial 扩展 | 关系型数据库，支持空间计算 (ST_Point, ST_DWithin, ST_Buffer 等) |
| **pandas 2.3.3** | 数据处理与分析 |
| **WSS (EMSC)** | 实时数据源：欧洲地中海地震中心 WebSocket |

### 前端

| 技术 | 用途 |
|------|------|
| **Vue 3.5.24** (Composition API) | 前端框架 |
| **Vite 7.2.5** (rolldown-vite) | 构建工具 |
| **Element Plus 2.11.8** | UI 组件库 |
| **ECharts 6.0.0** | 地图可视化（散点图、热力图、轨迹线） |
| **Axios 1.13.2** | HTTP 客户端 |
| **dayjs 1.11.19** | 日期格式化 |
| **pnpm** | 包管理器 |

## 核心功能

### 1. 实时数据采集

- **WebSocket 客户端** (`listener.py`) 连接到 `wss://www.seismicportal.eu/standing_order/websocket`
- 解析 EMSC 推送的地震事件 JSON，通过 `database.insert_earthquake()` 写入 DuckDB
- 支持断线自动重连、定时重启（默认 3600 秒）

### 2. 数据存储与空间查询

- **DuckDB** + spatial 扩展存储地震数据，支持 WGS84 坐标系统
- `EarthquakeQuery` 构建器支持链式调用：`since()` → `within_radius()` → `to_geojson()`
- 支持查询类型：
  - **最近 N 小时** 事件列表
  - **圆形范围** 查询（半径 km）
  - **矩形范围** 查询（BBOX）
  - **叠加分析**（WKT/GeoJSON 几何相交）
  - **最近邻** 查询（ST_Distance_Sphere）
  - **缓冲区分析**（ST_Buffer）
  - **网格聚类**统计

### 3. 风险评估引擎

特征工程 (`analysis/feature_builder.py`)：
- 计算近期窗口统计（最近 7 天区域事件数、平均震级）
- 计算历史基线（过去 3 年区域日均事件数、标准差）
- 计算异常分数：`(近期计数 - 期望计数) / 标准差`

风险评分 (`analysis/risk_scorer.py`)：
- 四维加权模型：震级(40%) + 深度(20%) + 活跃度(20%) + 异常(20%)
- 三级风险等级：HIGH (≥65) / MEDIUM (≥40) / LOW

### 4. 前端可视化

- **世界地图**：ECharts geo 世界地图，支持 roams 缩放平移
- **可视化模式**：普通散点图 / 热力图 / 聚类视图
- **时间轴回放**：滑块控制 + 播放按钮
- **GIS 功能**：
  - 板块边界叠加（ plates.json）
  - 缓冲区可视化
  - 最近邻连线
- **主题切换**：深色（默认）/ 浅色 / 地形
- **风险排行面板**：高风险事件列表 + 详情抽屉

### 5. 历史数据分析

- 历史时间线统计（按月/日聚合）
- 历史区域分布统计
- 震级分布柱状图
- 24 小时分布折线图

## 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/earthquakes` | GET | 最近地震列表 |
| `/earthquakes.geojson` | GET | GeoJSON 格式输出（支持圆形/矩形过滤） |
| `/earthquakes/near` | GET | 圆形范围查询 |
| `/earthquakes/nearest` | GET | 最近邻查询 |
| `/earthquakes/buffer` | GET | 缓冲区分析 |
| `/earthquakes/overlay` | GET | 几何叠加分析 |
| `/stats/cluster` | GET | 网格聚类统计 |
| `/stats/region` | GET | 区域统计 |
| `/stats/magnitude-distribution` | GET | 震级分布 |
| `/stats/hourly-distribution` | GET | 小时分布 |
| `/stats/history/timeline` | GET | 历史时间线 |
| `/stats/history/region_dist` | GET | 历史区域分布 |
| `/risk/ranking` | GET | 风险排行 |
| `/risk/events/<unid>` | GET | 单事件风险详情 |

## 目录结构

```
earthquake/
├── backend/
│   ├── main.py              # 入口：Tornado IOLoop + Flask WSGIContainer
│   ├── api.py               # Flask API（20+ 端点）
│   ├── service.py           # 业务逻辑层
│   ├── database.py          # DuckDB 数据访问层（空间查询 + 特征/风险存储）
│   ├── config.py            # 配置管理（环境变量 + 默认值）
│   ├── listener.py          # WebSocket 实时采集（EMSC）
│   ├── init_db.py           # 数据库初始化
│   ├── manage.py            # 数据库管理工具
│   ├── earthquakes.csv      # 示例数据
│   ├── earthquakes.duckdb   # 数据库文件
│   ├── pyproject.toml       # Python 依赖
│   ├── analysis/
│   │   ├── feature_builder.py  # 特征工程
│   │   └── risk_scorer.py       # 风险评分
│   └── jobs/                # 批处理脚本
│       ├── import_history.py    # USGS 历史数据导入
│       ├── refresh_features.py # 批量特征刷新
│       └── score_risk.py        # 批量风险评分
├── frontend/
│   ├── src/
│   │   ├── App.vue              # 主应用组件
│   │   ├── main.js               # Vue 入口
│   │   ├── style.css            # 全局样式
│   │   ├── components/
│   │   │   ├── EarthquakeMap.vue # ECharts 地图组件
│   │   │   ├── RiskPanel.vue    # 风险面板
│   │   │   ├── Sidebar.vue      # 侧边栏（地震列表）
│   │   │   └── TopHeader.vue    # 顶部导航
│   │   └── utils/
│   │       └── formatters.js    # 格式化工具
│   ├── public/
│   │   ├── world.json           # 世界地图 GeoJSON
│   │   └── plates.json          # 板块边界数据
│   ├── index.html
│   ├── package.json
│   └── vite.config.js            # Vite 配置（代理 /earthquakes 等到 :5000）
├── 运行说明.md            # 操作说明
├── architecture.md       # 架构文档
├── plan.md               # MVP 计划
└── progress.md           # 进度追踪
```

## 快速启动

### 后端

```bash
cd backend
uv run main.py
# Flask API: http://localhost:5000
# WebSocket 监听器同时启动
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev
# 访问 http://localhost:5173
```

## 数据模型

### earthquakes（地震事件表）

| 字段 | 类型 | 说明 |
|------|------|------|
| unid | VARCHAR | 主键（EMSC 事件 ID） |
| time | TIMESTAMP | 发震时间 |
| latitude/longitude | DOUBLE | 坐标 |
| depth | DOUBLE | 震源深度（km） |
| magnitude | DOUBLE | 震级 |
| region | VARCHAR | 地区名称 |
| geom | GEOMETRY | 空间几何（ST_Point） |
| is_realtime | BOOLEAN | 是否实时数据 |

### earthquake_features（事件特征表）

缓存事件特征：`recent_window_hours`、`recent_region_event_count`、`historical_avg_daily_count`、`anomaly_score` 等

### earthquake_risk_scores（风险评分表）

存储风险评分结果：`risk_score`、`risk_level`（HIGH/MEDIUM/LOW）、四个分量得分、`explanation` 自然语言解释

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EARTHQUAKE_DB_PATH` | `backend/earthquakes.duckdb` | 数据库路径 |
| `EARTHQUAKE_DEFAULT_QUERY_HOURS` | `48` | 默认查询窗口 |
| `EARTHQUAKE_RISK_WEIGHT_MAGNITUDE` | `0.4` | 震级权重 |
| `EARTHQUAKE_RISK_WEIGHT_DEPTH` | `0.2` | 深度权重 |
| `EARTHQUAKE_RISK_WEIGHT_ACTIVITY` | `0.2` | 活跃度权重 |
| `EARTHQUAKE_RISK_WEIGHT_ANOMALY` | `0.2` | 异常分数权重 |
| `EARTHQUAKE_RISK_LEVEL_HIGH_THRESHOLD` | `65` | HIGH 阈值 |
| `EARTHQUAKE_RISK_LEVEL_MEDIUM_THRESHOLD` | `40` | MEDIUM 阈值 |
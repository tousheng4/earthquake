# 项目文件结构与职责

```text
earthquake/
  AGENTS.md                       协作规则文件，规定开发前阅读文档和重大功能后更新进度
  architecture.md                 项目文件结构与职责说明
  plan.md                         MVP 实施计划，定义开发步骤和验收方式
  progress.md                     开发进度记录，记录已完成工作和验证结果
  运行说明.md                      项目运行文档，说明前后端启动和基础验证方法
  Point.md                        项目展示要点文档
  ppt.md                          演示或答辩材料草稿
  require.md                      需求说明文档
  演讲稿.md                        答辩或演示讲稿
  backend/
    analysis/
      __init__.py                 分析模块包入口
      feature_builder.py          第一版事件特征构建逻辑，负责按窗口和历史基线生成特征行
      risk_scorer.py              第一版规则型风险评分逻辑，负责生成分数、等级和解释
    .python-version               Python 版本提示文件
    README.md                     后端目录说明文件
    api.py                        REST 接口层，解析请求并返回 JSON，包括历史统计接口
                                 现已包含风险排行和单事件风险详情接口
    config.py                     统一配置文件，管理数据库路径和默认参数
                                 并集中管理风险评分权重、等级阈值和版本号
    database.py                   数据访问层，负责 DuckDB 连接、写入、空间查询、实时统计和历史统计查询
                                 并提供事件特征缓存与风险评分缓存的读写入口
    earthquakes.csv               仓库中的地震样例或辅助数据文件
    earthquakes.duckdb            DuckDB 主数据库文件
    earthquakes.duckdb.wal        DuckDB WAL 日志文件
    init_db.py                    数据库初始化脚本，用于建库、建表、补字段和建索引
    listener.log                  实时监听运行日志
    listener.py                   实时监听模块，连接外部 WebSocket 并写入地震事件
    main.py                       后端启动入口，启动 Tornado、Flask API 和监听任务
    manage.py                     轻量数据库管理脚本，用于快速初始化数据库结构
                                 包含事件特征缓存表的最小建表逻辑
    pyproject.toml                后端依赖配置文件
    service.py                    业务逻辑层，负责组织查询和整理接口输出，包括历史统计结果
                                 现已负责风险排行与风险详情结构整理
    uv.lock                       uv 依赖锁文件
    jobs/
      import_history.py           历史数据导入脚本，用于从本地 CSV 导入历史地震数据并去重入库
      migrate_event_schema.py     事件表结构迁移脚本，用于补齐统一事件层字段并回填旧数据
      refresh_features.py         特征刷新任务脚本，用于按时间窗口批量构建并写入事件特征
      score_risk.py               风险评分任务脚本，用于批量生成事件风险评分结果
  frontend/
    README.md                     前端目录说明文件
    index.html                    前端 HTML 入口文件
    package.json                  前端依赖和脚本配置文件
    pnpm-lock.yaml                pnpm 依赖锁文件
    vite.config.js                Vite 配置文件，负责开发服务和代理配置
    public/
      plates.json                 板块边界数据
      world.json                  世界地图边界数据
    src/
      App.vue                     前端页面总装配文件，负责组织页面主要组件
      main.js                     Vue 应用入口文件，负责挂载应用和注册插件
      style.css                   前端全局样式文件
      utils/
        formatters.js             前端格式化工具，处理时间、颜色、经纬度等展示格式
      components/
        EarthquakeMap.vue         地图核心组件，负责地震点和 GIS 图层交互
        Sidebar.vue               侧边栏组件，负责统计卡片、筛选项和地震列表展示
        TopHeader.vue             顶部控制栏组件
```

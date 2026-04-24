# 开发进度记录

## 当前状态

- 已完成 `plan.md` 中的第一步：项目基线整理
- 已完成 `plan.md` 中的第二步：统一配置入口

## 本轮完成内容

### 已阅读文档

本轮为完成第一步，已阅读当前目录中的文档：

- `AGENTS.md`
- `architecture.md`
- `plan.md`
- `Point.md`
- `ppt.md`
- `require.md`
- `演讲稿.md`

### 已完成工作

1. 梳理了当前项目的真实主链路：
   `listener.py -> database.py -> service.py -> api.py -> Vue 前端`
2. 梳理了当前前后端启动方式、默认端口与代理关系
3. 梳理了当前核心数据库文件、核心表与已有接口能力
4. 新增了面向后续开发者的基线文档 `运行说明.md`
5. 更新了 `architecture.md`，补充了当前文件职责和第一步后的架构理解
6. 新增统一配置文件 `backend/config.py`
7. 将数据库路径和部分关键 API 默认参数接入统一配置

### 本轮新增文件

- `运行说明.md`
- `backend/config.py`

## 本轮涉及文件

- `运行说明.md`
- `backend/config.py`
- `architecture.md`
- `progress.md`
- `backend/api.py`
- `backend/database.py`

## 当前结论

### 当前项目已经具备的基础能力

- 实时地震 WebSocket 接入链路已跑通
- DuckDB + Spatial 的空间查询能力已可用
- Flask REST 接口已提供事件查询和基础统计能力
- Vue3 + ECharts 前端已具备地图、热力图、时间轴、聚类、缓冲区、最近邻等展示能力

### 当前项目最明显的短板

- 历史数据底座不足
- 分析层能力不足
- 辅助决策输出不足

### 当前最适合优先补的方向

- 历史数据回灌
- 统一数据层建设
- 特征构建
- 风险评分

### 当前不建议做的事情

- 不建议推翻现有主链路
- 不建议优先做复杂前端美化
- 不建议在没有历史基线前直接做复杂模型

## 测试说明

按协作分工，本轮测试由人工执行。

第一步建议人工验证：

- 后端可以正常启动
- 前端可以正常启动
- 页面地图可以正常显示
- 至少一个地震接口返回正常
- 至少一个统计接口返回正常

第二步建议人工验证：

- 后端仍然可以正常启动
- 不传 `hours` 参数时，`/earthquakes`、`/stats/cluster` 等接口仍能正常返回
- 修改 `backend/config.py` 中的 `DEFAULT_QUERY_HOURS` 后，不传 `hours` 参数的相关接口默认行为会发生变化
- 修改 `backend/config.py` 中的 `DATABASE_PATH` 后，后端仍能从新的数据库路径读取
- 未额外设置环境变量时，项目仍使用当前默认配置正常工作

## 给后续开发者的提示

1. 开始任何代码修改前，先完整阅读 `architecture.md` 和 `plan.md`
2. 当前已经完成统一配置入口，但只接入了最必要的地方，属于刻意控制范围的最小实现
3. 当前配置主要接入了数据库路径和若干关键默认查询参数，尚未对所有旧文件做全面改造
4. 下一步应严格进入 `plan.md` 的第三步：统一事件表最小扩展
5. 不要在第三步顺手推进历史导入、风险评分或前端改造
6. 每完成一个重大功能后，继续更新本文件
## 第三步完成记录：统一事件表最小扩展

### 本步目标
- 在不破坏现有实时监听和旧查询接口的前提下，为 `earthquakes` 表补齐统一事件层所需的最小字段。

### 本步修改的文件
- `backend/database.py`
- `backend/init_db.py`
- `backend/manage.py`
- `backend/jobs/migrate_event_schema.py`

### 本步新增或变更的能力
- 为 `earthquakes` 表补充了统一事件层字段：
  - `source`
  - `source_event_id`
  - `is_realtime`
  - `ingest_time`
- 实时写入逻辑现在会为上述字段写入默认值，不要求监听器立即改造。
- 初始化脚本和管理脚本现在都能创建或补齐这些字段。
- 新增了独立迁移任务 `backend/jobs/migrate_event_schema.py`，用于对已有数据库做结构扩展和历史数据回填。

### 本步自验证
- 运行 `uv run python jobs\\migrate_event_schema.py`
  - 结果：迁移成功，`DESCRIBE earthquakes` 中已出现新增字段。
- 运行 `uv run python -c "import database; print('import_ok')"`
  - 结果：`database.py` 可以正常导入。
- 运行旧查询校验
  - 结果：`get_recent_earthquakes(1)` 仍返回列表结果，说明旧查询链路未被破坏。
- 插入一条临时校验事件并检查新字段
  - 结果：`source='emsc'`、`source_event_id=unid`、`is_realtime=True`、`ingest_time` 非空。

### 本步结论
- 第三步已经达到可验收状态。
- 现有系统已经具备“实时事件 + 历史事件”共用同一事实表的最小结构基础。
- 当前仍未进入历史导入、历史统计、特征构建和风险评分阶段。

### 给后续开发者的提示
- 下一步应严格进入历史数据导入，而不是继续扩展表字段。
- 在导入脚本中应优先复用 `source`、`source_event_id`、`is_realtime`、`ingest_time`，避免再引入新的来源标识口径。
- 如果需要对已有数据库执行结构升级，优先运行 `uv run python jobs\\migrate_event_schema.py`，不要把迁移逻辑塞入 `uv run main.py` 的运行时主链路。

## 第四步完成记录：历史数据导入任务

### 本步目标
- 为系统增加一个最小可用的历史地震导入任务。
- 先支持单一本地 CSV 数据源，确保导入、标准化、按时间范围过滤和去重入库可以跑通。

### 本步修改的文件
- `backend/config.py`
- `backend/jobs/import_history.py`
- `architecture.md`
- `progress.md`

### 本步新增或变更的能力
- 在 `backend/config.py` 中新增历史导入相关配置：
  - `DEFAULT_HISTORY_IMPORT_SOURCE_PATH`
  - `DEFAULT_HISTORY_IMPORT_SOURCE_NAME`
  - `DEFAULT_HISTORY_IMPORT_BATCH_SIZE`
- 新增 `backend/jobs/import_history.py`
  - 支持从本地 CSV 读取历史地震数据
  - 支持字段映射和基础标准化
  - 支持按最近 N 年过滤
  - 支持文件内去重
  - 支持基于 `unid` 的数据库去重
  - 支持重复执行
  - 输出导入统计信息

### 本步自验证
- 使用临时数据库执行 `uv run python init_db.py`
  - 结果：测试数据库初始化成功。
- 执行 `uv run python -m py_compile jobs\\import_history.py`
  - 结果：脚本语法检查通过。
- 首次执行 `uv run python jobs\\import_history.py --source-path earthquakes.csv --years 3`
  - 结果：`fetched_rows=13`，`inserted_rows=13`，`failed_rows=0`
- 第二次执行相同导入命令
  - 结果：`inserted_rows=0`，`skipped_existing=13`
- 查询临时数据库
  - 结果：总记录数为 13，历史记录数为 13，样例记录字段为 `source='history_csv'`、`is_realtime=False`

### 本步结论
- 第四步已经达到可验收状态。
- 当前系统已经具备最小历史回灌能力，并且支持重复执行不产生重复数据。
- 这一步仍然只实现了单一本地 CSV 数据源，没有扩展到远程历史数据源。

### 给后续开发者的提示
- 下一步应严格进入历史统计接口，不要在这一轮继续扩展多数据源导入。
- 如果后续接入远程历史源，优先复用 `import_history.py` 中的标准化和去重口径，而不是重写另一套入库逻辑。
- 自验证历史导入时，优先使用临时 DuckDB 路径，避免污染主库。

## 第五步完成记录：历史统计接口

### 本步目标
- 基于已经导入的历史地震数据，增加最小可用的历史统计接口。
- 先支持历史时间分布和历史区域分布两类查询，返回适合前端图表直接消费的简单结构。

### 本步修改的文件
- `backend/database.py`
- `backend/service.py`
- `backend/api.py`
- `architecture.md`
- `progress.md`

### 本步新增或变更的能力
- 在 `backend/database.py` 中新增：
  - `history_timeline`
  - `history_region_distribution`
- 在 `backend/service.py` 中新增：
  - `history_timeline`
  - `history_region_distribution`
- 在 `backend/api.py` 中新增接口：
  - `/stats/history/timeline`
  - `/stats/history/region_dist`

### 新接口说明
- `/stats/history/timeline`
  - 作用：按月或按日聚合历史事件数量
  - 主要参数：
    - `years`
    - `bucket=month|day`
- `/stats/history/region_dist`
  - 作用：统计历史事件的区域分布
  - 主要参数：
    - `years`
    - `limit`

### 本步自验证
- 执行 `uv run python -m py_compile api.py service.py database.py`
  - 结果：语法检查通过。
- 使用临时数据库执行 `uv run python init_db.py`
  - 结果：测试数据库初始化成功。
- 使用临时数据库执行 `uv run python jobs\\import_history.py --source-path earthquakes.csv --years 3`
  - 结果：样例历史数据成功导入。
- 使用 Flask 测试客户端请求新接口
  - `/stats/history/timeline?years=3&bucket=month`
    - 结果：返回 `200`，返回值为列表，样例首条为 `{'bucket_start': '2025-10-01', 'event_count': 1}`
  - `/stats/history/region_dist?years=3&limit=5`
    - 结果：返回 `200`，返回值为列表，样例首条为 `{'event_count': 4, 'region': 'WESTERN TURKEY'}`

### 本步结论
- 第五步已经达到可验收状态。
- 系统现在已经具备最小历史统计能力，可以支撑后续历史图表和异常分析观察入口。
- 当前仍未进入特征构建和风险评分阶段。

### 给后续开发者的提示
- 下一步应严格进入特征构建，不要在这一轮继续扩展更多历史统计维度。
- 前端接入历史图表时，优先直接消费这两个接口返回的列表结果，不要先做过度封装。

## 第六步完成记录：建立事件特征缓存层

### 本步目标
- 为后续风险评分准备第一版结构化特征存储。
- 先建立事件特征缓存表和最小读写入口，不提前把风险接口和前端展示混进来。

### 本步修改的文件
- `backend/config.py`
- `backend/init_db.py`
- `backend/manage.py`
- `backend/database.py`
- `architecture.md`
- `progress.md`

### 本步新增或变更的能力
- 在 `backend/config.py` 中新增特征构建相关配置：
  - `DEFAULT_FEATURE_RECENT_WINDOW_HOURS`
  - `DEFAULT_FEATURE_BASELINE_YEARS`
  - `DEFAULT_FEATURE_BATCH_LIMIT`
  - `FEATURE_SCHEMA_VERSION`
- 在数据库中新增 `earthquake_features` 表，用于缓存事件级特征：
  - 事件基础字段：`event_unid`、`event_time`、`region`、`magnitude`、`depth`
  - 当前窗口特征：`recent_window_hours`、`recent_region_event_count`、`recent_region_avg_magnitude`
  - 历史基线特征：`historical_baseline_years`、`historical_region_event_count`
  - 历史统计特征：`historical_avg_daily_count`、`historical_daily_count_stddev`
  - 异常特征：`anomaly_score`
  - 缓存元数据：`feature_version`、`refreshed_at`
- 在 `backend/database.py` 中新增最小特征访问层：
  - `list_feature_candidates`
  - `upsert_earthquake_features`
  - `get_event_feature`
  - `list_event_features`
- 初始化脚本和管理脚本现在都能直接创建特征缓存表与索引。

### 本步自验证
- 执行 `uv run python -m py_compile config.py init_db.py manage.py database.py`
  - 结果：语法检查通过。
- 使用单进程临时数据库执行建表与特征写读校验
  - 结果：`earthquake_features` 表可以成功创建。
  - 结果：写入两条样例特征后，`upsert_earthquake_features` 返回 `2`。
  - 结果：`list_event_features(limit=5)` 返回 2 条记录。
  - 结果：`get_event_feature('feature_test_event_1')` 可正确读回区域 `WESTERN TURKEY`。

### 本步结论
- 第六步的目标已经落到可验证代码结构。
- 当前系统已经具备承接“事件特征结果”的最小缓存层，但还没有进入批量特征刷新任务和风险评分阶段。

### 给后续开发者的提示
- 下一步应严格进入“实现特征构建任务”，将具体计算逻辑放入分析模块，把任务文件作为调度入口。
- 风险评分应继续复用本步已经固定下来的特征字段口径，避免在后续步骤中重新发明一套命名。

## 第七步完成记录：实现特征构建任务

### 本步目标
- 为近期重点事件补充可重复执行的特征刷新流程。
- 将复杂特征计算放进分析模块，任务脚本只负责调度和输出统计结果。

### 本步修改的文件
- `backend/analysis/__init__.py`
- `backend/analysis/feature_builder.py`
- `backend/jobs/refresh_features.py`
- `architecture.md`
- `progress.md`

### 本步新增或变更的能力
- 新增分析模块 `backend/analysis/feature_builder.py`
  - 支持基于事件时间和区域计算第一版特征行
  - 当前窗口特征包括：
    - `recent_region_event_count`
    - `recent_region_avg_magnitude`
  - 历史基线特征包括：
    - `historical_region_event_count`
    - `historical_avg_daily_count`
    - `historical_daily_count_stddev`
  - 支持生成 `anomaly_score`
- 新增任务脚本 `backend/jobs/refresh_features.py`
  - 支持通过 `--hours` 指定刷新时间窗口
  - 支持通过 `--limit` 控制单次处理事件数
  - 支持通过 `--baseline-years` 指定历史基线范围
  - 输出候选数、处理数、写入数、失败数和耗时
- 特征刷新流程现在可以复用第六步建立的 `earthquake_features` 缓存表，重复执行时走 upsert 而不是重复插入。

### 本步自验证
- 执行 `uv run python -m py_compile analysis\\__init__.py analysis\\feature_builder.py jobs\\refresh_features.py database.py config.py init_db.py manage.py`
  - 结果：语法检查通过。
- 使用临时数据库执行初始化、历史导入和两次特征刷新
  - 结果：首轮 `candidate_rows=13`、`processed_rows=13`、`written_rows=13`、`failed_rows=0`
  - 结果：第二轮对相同窗口重复刷新后，仍为 `candidate_rows=13`、`processed_rows=13`、`written_rows=13`、`failed_rows=0`
  - 结果：`list_event_features(limit=20)` 可查到 13 条特征记录
- 抽查三个不同区域的样例特征
  - 结果：`PHILIPPINE ISLANDS REGION`、`FIJI REGION`、`BABUYAN ISL REGION  PHILIPPINES` 的 `recent_region_avg_magnitude` 分别为 `4.1`、`4.5`、`4.4`，说明特征值不是统一默认值

### 本步结论
- 第七步已经达到可验收状态。
- 当前系统已经具备面向近期事件的批量特征构建能力，并且刷新流程可重复执行。
- 当前仍未进入风险评分、风险接口和前端风险面板阶段。

### 给后续开发者的提示
- 下一步应严格进入“第一版规则型风险评分”，优先复用当前特征缓存表，不要重新临时拼装特征。
- 风险评分解释文本应以当前特征字段为基础组织，保持后续接口、报告和前端口径一致。

## 第八步完成记录：实现第一版规则型风险评分

### 本步目标
- 基于已构建的事件特征，生成第一版可解释的规则型风险评分。
- 输出综合分数、风险等级和自然语言解释，并让权重配置真正参与评分。

### 本步修改的文件
- `backend/config.py`
- `backend/init_db.py`
- `backend/manage.py`
- `backend/database.py`
- `backend/analysis/risk_scorer.py`
- `backend/jobs/score_risk.py`
- `architecture.md`
- `progress.md`

### 本步新增或变更的能力
- 在 `backend/config.py` 中补充风险评分配置：
  - `RISK_LEVEL_HIGH_THRESHOLD`
  - `RISK_LEVEL_MEDIUM_THRESHOLD`
  - `RISK_SCHEMA_VERSION`
- 在数据库中新增 `earthquake_risk_scores` 缓存表，用于保存事件评分结果：
  - `risk_score`
  - `risk_level`
  - `magnitude_component`
  - `depth_component`
  - `activity_component`
  - `anomaly_component`
  - `explanation`
  - `score_version`
  - `scored_at`
- 在 `backend/database.py` 中新增风险评分缓存读写入口：
  - `upsert_risk_scores`
  - `get_risk_score`
  - `list_risk_scores`
- 新增评分模块 `backend/analysis/risk_scorer.py`
  - 基于震级、深度、近期活跃度、异常程度四部分做规则加权
  - 生成 `low` / `medium` / `high` 风险等级
  - 生成可直接用于答辩或报告的自然语言解释
- 新增任务脚本 `backend/jobs/score_risk.py`
  - 支持按批次对已缓存的事件特征执行评分
  - 输出候选数、处理数、写入数、失败数和耗时

### 本步自验证
- 执行 `uv run python -m py_compile analysis\\__init__.py analysis\\feature_builder.py analysis\\risk_scorer.py jobs\\refresh_features.py jobs\\score_risk.py database.py config.py init_db.py manage.py`
  - 结果：语法检查通过。
- 使用临时数据库执行初始化、历史导入、特征刷新和风险评分
  - 结果：`import_inserted_rows=13`
  - 结果：`feature_written_rows=13`
  - 结果：评分任务 `candidate_rows=13`、`processed_rows=13`、`written_rows=13`、`failed_rows=0`
  - 结果：`list_risk_scores(limit=5)` 可返回评分结果，样例最高分为 `44.5`，等级为 `medium`，且解释文本非空
- 使用人工构造的高风险/低风险样例比较评分
  - 结果：高风险样例得分 `85.2`、等级 `high`
  - 结果：低风险样例得分 `24.5`、等级 `low`
  - 结果：高风险样例得分显著高于低风险样例
- 验证权重配置生效
  - 结果：同一测试事件在默认权重下得分为 `61.3333`
  - 结果：将震级权重上调后得分变为 `68.1667`
  - 结果：说明评分结果会随配置变化而合理变化

### 本步结论
- 第八步已经达到可验收状态。
- 当前系统已经具备稳定、可解释、可调参的第一版风险评分能力。
- 当前仍未进入风险查询接口和前端风险面板阶段。

### 给后续开发者的提示
- 下一步应严格进入“新增风险查询接口”，优先直接复用 `earthquake_risk_scores` 和 `earthquake_features` 两层缓存结果。
- 风险接口中的详情返回应尽量保留本步生成的评分解释原文，避免前后端出现两套解释口径。

## 第九步完成记录：新增风险查询接口

### 本步目标
- 将已有风险评分结果稳定暴露为后端查询接口。
- 提供高风险事件排行和单事件评估详情两个入口，并保证空数据和不存在事件时返回结构稳定。

### 本步修改的文件
- `backend/config.py`
- `backend/database.py`
- `backend/service.py`
- `backend/api.py`
- `architecture.md`
- `progress.md`

### 本步新增或变更的能力
- 在 `backend/config.py` 中新增：
  - `DEFAULT_RISK_QUERY_LIMIT`
- 在 `backend/database.py` 中新增：
  - `risk_ranking`
  - `risk_event_detail`
- 在 `backend/service.py` 中新增：
  - `risk_ranking`
  - `risk_event_detail`
- 在 `backend/api.py` 中新增接口：
  - `/risk/ranking`
  - `/risk/events/<event_unid>`

### 新接口说明
- `/risk/ranking`
  - 作用：返回按风险分数排序的事件列表
  - 主要参数：
    - `hours`
    - `limit`
    - `min_risk_level=low|medium|high`
- `/risk/events/<event_unid>`
  - 作用：返回指定事件的基础信息、特征摘要和风险评分详情
  - 主要返回块：
    - `event`
    - `feature_summary`
    - `risk`

### 本步自验证
- 执行 `uv run python -m py_compile api.py service.py database.py config.py init_db.py manage.py analysis\\risk_scorer.py jobs\\score_risk.py`
  - 结果：语法检查通过。
- 使用临时数据库执行初始化、历史导入、特征刷新、风险评分后，使用 Flask 测试客户端请求新接口
  - `/risk/ranking?hours=30000&limit=5&min_risk_level=low`
    - 结果：返回 `200`
    - 结果：返回 5 条记录，且记录中包含风险分量、事件时间、事件标识等字段
  - `/risk/events/<event_unid>`
    - 结果：返回 `200`
    - 结果：返回结构同时包含 `event`、`feature_summary`、`risk`
  - `/risk/events/not_found_event`
    - 结果：返回 `404`
    - 结果：返回体为 `{"error": "event not found"}`
  - `/risk/ranking?hours=30000&limit=5&min_risk_level=high`
    - 结果：返回 `200`
    - 结果：返回体结构稳定，为列表类型
- 使用空临时数据库直接请求 `/risk/ranking?hours=48&limit=5&min_risk_level=high`
  - 结果：返回 `200`
  - 结果：返回空列表 `[]`

### 本步结论
- 第九步已经达到可验收状态。
- 当前系统已经具备供前端和报告模块消费的最小风险查询接口。
- 当前仍未进入前端风险面板阶段。

### 给后续开发者的提示
- 下一步应严格进入“前端新增最小风险面板”，优先直接消费本步接口，不要先做过度封装。
- 前端详情展示应直接复用 `risk.explanation` 和 `feature_summary`，保持前后端字段口径一致。

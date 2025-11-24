使用 Python + Tornado WebSocket 客户端高并发消费 EMSC 实时地震流，基于事件 unid 去重和字段完整性校验清洗 JSON 消息并写入 DuckDB 高性能数据库。
通过 Flask 封装 REST 接口，提供近 48 小时数据的查询与过滤。
前端使用 Vue3 + Vite + ECharts 构建单页应用，基于 Geo 组件建立地理坐标系，叠加 GeoJSON 世界底图与构造板块矢量图层实现多层级 GIS 可视化。
借助 ECharts tooltip 与自定义 formatter 封装地震详情弹窗，以 HTML 形式展示 Magnitude / Region / Time / Depth 等详细信息。利用 visualMap 组件与 heatmap 图层实现地理空间密度分析，结合 Vue computed 响应式过滤与 setInterval 定时器驱动时空数据的动态演变回放。将后端网格聚合结果映射为 ECharts 散点图层，通过 symbolSize 与颜色梯度分别表征区域地震频次与平均震级。
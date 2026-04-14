## 1. 仪表盘模板重写

- [x] 1.1 重写 `render_dashboard_home()` — 返回 Bases YAML，包含 Today / Trending / 7-Day Trend 三个视图
- [x] 1.2 重写 `render_dashboard_trending()` — 返回 Bases YAML，包含 48h 热点 + 跨平台热点两个视图
- [x] 1.3 重写 `render_dashboard_reading_list()` — 返回 Bases YAML，包含未读列表 + 按分类浏览两个视图
- [x] 1.4 重写 `render_dashboard_people_tracker()` — 返回 Bases YAML，包含 People / Companies / Projects 三个视图
- [x] 1.5 新增 `render_dashboard_articles()` — 返回 Bases YAML，全量文章数据库视图，含 trend_score Average 汇总
- [x] 1.6 删除废弃的渲染函数：`render_dashboard_daily_stats`、`render_dashboard_weekly_stats`、`render_dashboard_knowledge_graph`、`render_dashboard_by_category`

## 2. 仪表盘输出适配

- [x] 2.1 修改 `ainews/publisher/dashboards.py`：`DASHBOARDS` 字典从 8 个减少为 5 个，文件名后缀改为 `.base`
- [x] 2.2 修改 `init_dashboards()` 输出路径：`AI-News/Dashboards/Home.base` 等格式
- [x] 2.3 修改 `rebuild_dashboards()` 确认覆盖 `.base` 文件

## 3. 每日笔记模板迁移

- [x] 3.1 重写 `render_daily_header()` — 将 Dataview 概览表替换为 `base` 嵌入代码块
- [x] 3.2 确认每日笔记仍为 `.md` 文件格式，`base` 代码块正确嵌入

## 4. 测试

- [x] 4.1 测试仪表盘 YAML 语法正确性：验证每个 `render_dashboard_*()` 返回的 YAML 可被 `yaml.safe_load` 解析
- [x] 4.2 测试仪表盘文件数量：验证 `init_dashboards` 生成恰好 5 个 `.base` 文件
- [x] 4.3 测试每日笔记嵌入：验证 `render_daily_header` 包含 `base` 代码块且无 `dataview` 代码块
- [x] 4.4 测试重建：验证 `rebuild_dashboards` 正确覆盖已有 `.base` 文件
- [x] 4.5 确认所有新代码测试覆盖率 >= 80%

## 5. 文档同步

- [x] 5.1 更新 `docs/06-obsidian-integration.md` 反映 Bases 迁移变更

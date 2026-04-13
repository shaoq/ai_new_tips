## ADDED Requirements

### Requirement: 仪表盘初始化
系统 SHALL 提供 `init_dashboards()` 函数，在 `AI-News/Dashboards/` 目录下创建 8 个 Dataview 仪表盘模板文件。每个文件为独立的 Markdown 文件，包含 Dataview 查询语句。

#### Scenario: 初始化仪表盘
- **WHEN** 执行 `ainews sync obsidian --init-dashboards`
- **THEN** 系统在 `{vault}/AI-News/Dashboards/` 下创建 Home.md、Trending.md、Daily-Stats.md、Weekly-Stats.md、Reading-List.md、People-Tracker.md、Knowledge-Graph.md、By-Category.md

#### Scenario: 仪表盘已存在
- **WHEN** 执行 `--init-dashboards` 且仪表盘文件已存在
- **THEN** 跳过已存在的文件，不覆盖（除非使用 `--rebuild-dashboards`）

#### Scenario: 重建仪表盘
- **WHEN** 执行 `ainews sync obsidian --rebuild-dashboards`
- **THEN** 覆盖所有 8 个仪表盘文件，即使已存在

### Requirement: Home.md 总览首页
Home.md SHALL 包含三个部分：今日概览（DataviewJS 统计今日新增、热点数、未读数和分类分布）、今日热点（Dataview 表格列出当日 is_trending 文章）、最近 7 天趋势（DataviewJS 按日统计文章数）。

#### Scenario: Home.md 内容
- **WHEN** 用户打开 Home.md
- **THEN** Dataview 查询自动展示今日概览统计、热点文章列表和 7 天趋势数据

### Requirement: Trending.md 当前热点
Trending.md SHALL 包含两个部分：近 48 小时热点文章（is_trending=true，按 trend_score DESC，LIMIT 20）、跨平台热点（platforms >= 3，7 天内，按平台数和 trend_score 排序）。

#### Scenario: Trending.md 内容
- **WHEN** 用户打开 Trending.md
- **THEN** Dataview 查询自动展示 48h 内热点和跨平台热点文章

### Requirement: Daily-Stats.md 每日统计
Daily-Stats.md SHALL 包含来源分布（DataviewJS 按来源统计文章数和占比）和分类分布（Dataview 按分类统计数量和平均评分）。

#### Scenario: Daily-Stats.md 内容
- **WHEN** 用户打开 Daily-Stats.md
- **THEN** Dataview 查询自动展示当日来源分布表和分类分布表

### Requirement: Weekly-Stats.md 周统计
Weekly-Stats.md SHALL 包含本周概览（DataviewJS 统计 7 天内文章总数、热点数、新实体数）和每日文章数（Dataview 按日分组统计）。

#### Scenario: Weekly-Stats.md 内容
- **WHEN** 用户打开 Weekly-Stats.md
- **THEN** Dataview 查询自动展示本周概览和每日文章数统计

### Requirement: Reading-List.md 未读列表
Reading-List.md SHALL 包含未读文章列表（status=unread，按 relevance DESC，LIMIT 50）和本周未读热点（unread + is_trending，7 天内）。

#### Scenario: Reading-List.md 内容
- **WHEN** 用户打开 Reading-List.md
- **THEN** Dataview 查询自动展示按评分排序的未读文章列表和未读热点

### Requirement: People-Tracker.md 人物追踪
People-Tracker.md SHALL 包含活跃度 Top 20（30 天内，按提及次数排序）和新发现人物（7 天内首次出现）。

#### Scenario: People-Tracker.md 内容
- **WHEN** 用户打开 People-Tracker.md
- **THEN** Dataview 查询自动展示活跃人物排名和本周新发现人物

### Requirement: Knowledge-Graph.md 知识图谱
Knowledge-Graph.md SHALL 包含知识图谱说明（Obsidian Graph View 入口）和三个快捷入口列表：人物（mention_count DESC，LIMIT 30）、公司（mention_count DESC，LIMIT 20）、项目（mention_count DESC，LIMIT 20）。

#### Scenario: Knowledge-Graph.md 内容
- **WHEN** 用户打开 Knowledge-Graph.md
- **THEN** 页面显示 Graph View 说明和按提及次数排序的实体列表

### Requirement: By-Category.md 分类视图
By-Category.md SHALL 为每个分类（Industry/Research/Tools/Safety/Policy）生成独立 Dataview 表格，显示该分类下最近 30 天的文章（标题、评分、日期、来源）。

#### Scenario: By-Category.md 内容
- **WHEN** 用户打开 By-Category.md
- **THEN** Dataview 查询按分类展示最近 30 天的文章列表

### Requirement: 仪表盘目录自动创建
初始化仪表盘时，系统 SHALL 自动创建 `AI-News/Dashboards/` 目录（如不存在）。

#### Scenario: 目录不存在
- **WHEN** `AI-News/Dashboards/` 目录不存在
- **THEN** 系统自动创建目录后再写入仪表盘文件

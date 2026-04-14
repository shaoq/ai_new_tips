# Obsidian 集成方案

## 前置条件

### 需安装的插件

| 插件 | 用途 | 安装方式 |
|------|------|---------|
| **Local REST API** | 程序化读写 Vault | Settings → Community plugins → Browse → 搜索 "Local REST API" → Install → Enable |

> **注意**: 仪表盘和每日笔记使用 Obsidian 1.9+ 原生 **Bases** 功能，无需安装 Dataview 插件。

### 获取 API Key

```
Settings → Community plugins (左侧栏底部) → Local REST API → 复制 API Key
```

### 验证连接

```bash
# 检查服务状态 (无需认证)
curl -k https://127.0.0.1:27124/

# 列出 Vault 文件
curl -k -H "Authorization: Bearer YOUR_KEY" https://127.0.0.1:27124/vault/
```

### 默认配置

| 项目 | 值 |
|------|-----|
| HTTPS 端口 | 27124 |
| HTTP 端口 | 27123 |
| 绑定地址 | 127.0.0.1 (仅本地) |
| 协议 | HTTPS (自签名证书) |
| 认证 | Bearer Token |

**Obsidian 必须运行中**，插件随 Obsidian 进程启动。

> **重要：API 路径前缀说明**
>
> Obsidian Local REST API 插件 v3.x **不使用 `/v0` 前缀**。API 路径直接为 `/vault/...`、`/periodic/daily/`、`/search/simple/` 等。
> 早期代码中曾误设 `API_PREFIX = "/v0"`，导致所有 PUT 请求返回 404。已修正为 `API_PREFIX = ""`。
> 如果你在使用中遇到 404 错误，请首先检查 API 路径中是否包含了多余的前缀。

## 写入策略

### 写入方式

```
优先: Obsidian Local REST API
  ├─ 精确写入特定 heading
  ├─ 更新 frontmatter 字段
  ├─ 搜索已有内容 (去重)
  └─ 执行查询

兜底: 直接文件系统写入
  ├─ 当 Obsidian 未运行时自动降级
  ├─ 写入 .md 文件到 Vault 目录
  └─ Obsidian 下次启动自动检测新文件
```

### API 操作映射

| 操作 | REST API 调用 |
|------|-------------|
| 创建文章 | `PUT /vault/AI-News/{category}/{date-slug}.md` |
| 追加每日笔记 | `PATCH /periodic/daily/` + `Target-Type: heading` + `Operation: append` |
| 标记已读 | `PATCH /vault/{path}` + `Target-Type: frontmatter` + `Target: status` |
| 搜索重复 | `POST /search/simple/` |
| 创建实体页 | `PUT /vault/AI-News/Entities/{type}/{name}.md` |
| 创建仪表盘 | `PUT /vault/AI-News/Dashboards/{name}.base` |
| 检查连接 | `GET /` |

## Vault 目录结构

```
Vault/
  AI-News/                              ← 订阅专区根目录
    ├── Inbox/                          ← 待处理的文章 (备用)
    ├── Industry/                       ← 按分类归档
    │   └── 2026-04-13-openai-gpt6.md
    ├── Research/
    │   └── 2026-04-13-sparse-attn-v2.md
    ├── Tools/
    │   └── 2026-04-13-new-coding-agent.md
    ├── Safety/
    ├── Policy/
    │
    ├── Daily/                          ← 每日汇总 (.md，内嵌 base 代码块)
    │   ├── 2026-04-13.md
    │   ├── 2026-04-14.md
    │   └── ...
    │
    ├── Weekly/                         ← 周报
    │   ├── 2026-W15.md
    │   └── ...
    │
    ├── Entities/                       ← 实体页面 (知识图谱节点)
    │   ├── People/
    │   │   ├── Sam-Altman.md
    │   │   ├── Dario-Amodei.md
    │   │   └── Jane-Smith.md
    │   ├── Companies/
    │   │   ├── OpenAI.md
    │   │   └── DeepSeek.md
    │   └── Projects/
    │       ├── GPT-6.md
    │       └── Llama-4.md
    │
    ├── Dashboards/                     ← 仪表盘 (Obsidian Bases .base 文件)
    │   ├── Home.base                   ← 总览首页 (Today / Trending / 7-Day)
    │   ├── Trending.base               ← 热点 (48h / 跨平台)
    │   ├── Reading-List.base           ← 未读列表 + 按分类
    │   ├── People-Tracker.base         ← 实体追踪 (People / Companies / Projects)
    │   └── Articles.base               ← 全量文章数据库 + 汇总统计
    │
    └── Templates/                      ← 模板
        ├── article-template.md
        ├── entity-template.md
        └── daily-template.md
```

## 文章文件格式

```markdown
---
title: "GPT-6 发布：实时推理能力重大突破"
date: 2026-04-13
source: https://openai.com/blog/gpt-6
source_name: OpenAI Blog
author: Sam Altman
tags: [ai, llm, gpt-6, industry, openai, reasoning]
category: industry
status: unread
relevance: 9
trend_score: 8.7
is_trending: true
summary: "OpenAI发布GPT-6，具备实时多步推理能力，
         在数学、编程和科学推理基准上大幅超越前代模型。"
platforms: [hackernews, reddit, rss]
entities:
  people: [Sam Altman, Mark Chen]
  companies: [OpenAI]
  projects: [GPT-6]
  tech: [real-time reasoning, chain-of-thought]
imported_at: 2026-04-13T08:30:00Z
dingtalk_sent: true
---

# GPT-6 发布：实时推理能力重大突破

## 中文摘要
OpenAI 于今日正式发布 GPT-6 模型，最显著的突破是实现了
实时多步推理能力。该模型在 GSM8K、HumanEval 和 MATH
基准测试中分别达到 97.2%、96.8% 和 94.5% 的准确率。

## 原文链接
[阅读原文](https://openai.com/blog/gpt-6)

## 关联
- 涉及人物: [[Sam-Altman]], [[Mark-Chen]]
- 涉及公司: [[OpenAI]]
- 涉及项目: [[GPT-6]]
```

## 每日笔记格式

每日笔记为 `.md` 文件，内嵌 `base` 代码块显示当日文章概览：

```markdown
# AI News - 2026-04-13

## 概览

```base
filters:
  folder: AI-News
  date: "2026-04-13"
properties:
  relevance:
    type: number
  source_name:
    type: text
  category:
    type: select
  status:
    type: select
    options: [unread, reading, read]
views:
  default:
    name: Overview
    sort: trend_score DESC
    columns:
      - file.name
      - relevance
      - source_name
      - category
      - status
```

## 08:00 更新 (10篇)
- [[2026-04-13-openai-gpt6|GPT-6 发布]] 🔥 9.0 industry
- [[2026-04-13-sparse-attn|Sparse Attention V2]] 7.5 research
- [[2026-04-13-google-gemini|Gemini 2.5 Flash]] 7.0 industry
- ...

## 12:30 更新 (8篇)
- [[2026-04-13-deepseek-r2|DeepSeek R2 开源]] 🔥 8.5 industry
- ...
```

**关键机制:** 每次运行通过 `PATCH /periodic/daily/` + `Operation: append` 追加新段落，不影响已有内容。

## 仪表盘设计 (Obsidian Bases)

仪表盘使用 Obsidian 1.9+ 原生 **Bases** 功能，以 `.base` YAML 文件格式存储。无需安装第三方插件，支持多视图标签页、交互式编辑（如点击修改 status）。

### Home.base - 总览首页

```yaml
filters:
  folder: AI-News
properties:
  date: {type: date}
  relevance: {type: number}
  trend_score: {type: number}
  is_trending: {type: checkbox}
  status: {type: select, options: [unread, reading, read]}
  category: {type: select}
  source_name: {type: text}
views:
  today:
    name: Today
    filter: "date == today()"
    sort: trend_score DESC
    columns: [file.name, relevance, source_name, category, status]
  trending:
    name: Trending
    filter: "is_trending AND date >= today() - dur(1 day)"
    sort: trend_score DESC
    columns: [file.name, relevance, source_name, category]
  weekly:
    name: 7-Day Trend
    filter: "date >= today() - dur(7 days)"
    sort: "date DESC, trend_score DESC"
    columns: [file.name, date, relevance, source_name, category, is_trending]
```

### Trending.base - 热点追踪

```yaml
filters:
  folder: AI-News
properties:
  date: {type: date}
  relevance: {type: number}
  trend_score: {type: number}
  is_trending: {type: checkbox}
  category: {type: select}
  platforms: {type: list}
views:
  hot_48h:
    name: 48h Hot
    filter: "is_trending AND date >= today() - dur(2 days)"
    sort: trend_score DESC
    columns: [file.name, relevance, category, date]
  cross_platform:
    name: Cross-Platform
    filter: "length(platforms) >= 3 AND date >= today() - dur(7 days)"
    sort: "length(platforms) DESC, trend_score DESC"
    columns: [file.name, platforms, trend_score, category, date]
```

### Reading-List.base - 阅读列表

```yaml
filters:
  folder: AI-News
properties:
  date: {type: date}
  relevance: {type: number}
  status: {type: select, options: [unread, reading, read]}
  category: {type: select}
views:
  unread:
    name: Unread
    filter: "status == \"unread\""
    sort: relevance DESC
    columns: [file.name, relevance, category, date, status]
  by_category:
    name: By Category
    sort: "category ASC, relevance DESC"
    columns: [file.name, category, relevance, date, status]
    group_by: category
```

### People-Tracker.base - 实体追踪

```yaml
filters:
  folder: AI-News/Entities
properties:
  type: {type: select, options: [person, company, project, technology]}
  mention_count: {type: number}
  first_seen: {type: date}
  last_seen: {type: date}
views:
  people:
    name: People
    filter: "type == \"person\""
    sort: mention_count DESC
    columns: [file.name, mention_count, last_seen]
  companies:
    name: Companies
    filter: "type == \"company\""
    sort: mention_count DESC
    columns: [file.name, mention_count, last_seen]
  projects:
    name: Projects
    filter: "type == \"project\""
    sort: mention_count DESC
    columns: [file.name, mention_count, last_seen]
```

### Articles.base - 全量文章数据库

```yaml
filters:
  folder: AI-News
properties:
  date: {type: date}
  relevance: {type: number}
  trend_score: {type: number}
  is_trending: {type: checkbox}
  status: {type: select, options: [unread, reading, read]}
  category: {type: select}
  source_name: {type: text}
  platforms: {type: list}
summaries:
  total: {type: count}
  avg_relevance: {type: average, property: relevance}
  avg_trend_score: {type: average, property: trend_score}
views:
  all:
    name: All Articles
    sort: "date DESC, trend_score DESC"
    columns: [file.name, date, relevance, trend_score, category, source_name, status, is_trending]
  by_source:
    name: By Source
    sort: "source_name ASC, date DESC"
    columns: [source_name, file.name, date, relevance, category, status]
    group_by: source_name
```

## 交互式编辑

Bases 仪表盘支持直接在表格中交互式操作：

- **修改 status**: 点击 status 列的下拉菜单，直接切换 unread → reading → read
- **排序**: 点击列标题切换升序/降序
- **筛选**: 使用 Bases 内置筛选器
- **视图切换**: 点击标签页切换不同视图（Today / Trending / Weekly 等）

## 实体页面格式

```markdown
# Sam Altman

**类型**: person
**公司**: [[OpenAI]]
**首次出现**: 2026-04-01
**提及次数**: 28

## 相关文章
```dataview
LIST FROM "AI-News"
WHERE contains(entities.people, this.file.name)
SORT date DESC
LIMIT 10
```
```

> **注意**: 实体页面仍使用 Dataview `LIST` 查询关联文章，因为实体页面是 `.md` 文件且查询较简单。如需移除 Dataview 依赖，可将实体页面也迁移为 Bases 格式。

## 知识图谱说明

Obsidian 的 **Graph View** 天然支持知识图谱：
- 每篇文章通过 `[[双链]]` 关联到实体页面
- 每个实体页面反向关联到所有提到它的文章
- 人物 → 公司 → 项目 → 技术 → 文章 形成完整关联网络
- 随文章增长，图谱自动扩展，无需额外维护

## Bases 迁移说明

从 Dataview 迁移到原生 Bases 的变更：

| 项目 | 迁移前 (Dataview) | 迁移后 (Bases) |
|------|-------------------|----------------|
| 仪表盘数量 | 8 个 `.md` 文件 | 5 个 `.base` 文件 |
| 依赖插件 | Dataview + DataviewJS | 无 (Obsidian 1.9+ 原生) |
| 交互编辑 | 只读 | 支持直接编辑 status 等属性 |
| 视图切换 | 滚动页面 | 标签页切换 |
| 每日笔记 | `dataview` 代码块 | `base` 嵌入代码块 |
| 已删除仪表盘 | - | Daily-Stats, Weekly-Stats, Knowledge-Graph, By-Category |
| 新增仪表盘 | - | Articles (全量数据库+汇总) |

迁移后如需重建仪表盘，运行：
```bash
ainews sync obsidian --rebuild-dashboards
```

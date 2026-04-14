# Obsidian 集成方案

## 前置条件

### 需安装的插件

| 插件 | 用途 | 安装方式 |
|------|------|---------|
| **Local REST API** | 程序化读写 Vault | Settings → Community plugins → Browse → 搜索 "Local REST API" → Install → Enable |
| **Dataview** | 动态查询生成仪表盘 | Settings → Community plugins → Browse → 搜索 "Dataview" → Install → Enable |

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
  └─ 执行 Dataview 查询

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
    ├── Daily/                          ← 每日汇总
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
    ├── Dashboards/                     ← 仪表盘 (Dataview)
    │   ├── Home.md                     ← 总览首页
    │   ├── Trending.md                 ← 当前热点
    │   ├── Daily-Stats.md              ← 每日统计
    │   ├── Weekly-Stats.md             ← 周统计
    │   ├── Reading-List.md             ← 未读列表
    │   ├── People-Tracker.md           ← 人物追踪
    │   ├── Knowledge-Graph.md          ← 知识图谱入口
    │   └── By-Category.md              ← 分类视图
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

```markdown
# AI News - 2026-04-13

## 📊 今日概览
```dataview
TABLE relevance AS "评分", source_name AS "来源", category AS "分类"
FROM "AI-News"
WHERE date = date(today) AND status != "duplicate"
SORT trend_score DESC
```

## 08:00 更新 (10篇)
- [[2026-04-13-openai-gpt6|GPT-6 发布]] 🔥 9.0 industry
- [[2026-04-13-sparse-attn|Sparse Attention V2]] 7.5 research
- [[2026-04-13-google-gemini|Gemini 2.5 Flash]] 7.0 industry
- ...

## 12:30 更新 (8篇)
- [[2026-04-13-deepseek-r2|DeepSeek R2 开源]] 🔥 8.5 industry
- ...

## 20:00 更新 (5篇)
- [[2026-04-13-new-agent|新 AI 编程 Agent]] 6.0 tools
- ...

## 21:15 更新 (2篇)
- [[2026-04-13-qwen3|Qwen3 发布]] 7.0 industry
- ...
```

**关键机制:** 每次运行通过 `PATCH /periodic/daily/` + `Operation: append` 追加新段落，不影响已有内容。

## 仪表盘设计

### Home.md - 总览首页

```markdown
# AI News 订阅总览

## 📊 今日概览 (2026-04-13)

```dataviewjs
const today = dv.date("today");
const articles = dv.pages('"AI-News"')
  .where(p => p.date >= today && p.status != "duplicate");

const trending = articles.where(p => p.is_trending);
const byCategory = {};
for (const a of articles) {
  byCategory[a.category] = (byCategory[a.category] || 0) + 1;
}

dv.table(["指标", "数值"], [
  ["今日新增", articles.length],
  ["🔥 热点文章", trending.length],
  ["未读", articles.where(p => p.status == "unread").length],
]);

dv.table(["分类", "数量"],
  Object.entries(byCategory)
    .sort((a,b) => b[1] - a[1])
    .map(([k,v]) => [k, v])
);
```

## 🔥 今日热点

```dataview
TABLE relevance AS "评分", source_name AS "来源", category AS "分类"
FROM "AI-News"
WHERE date >= date(today) AND is_trending = true
SORT trend_score DESC
```

## 📅 最近 7 天趋势

```dataviewjs
const days = [];
for (let i = 6; i >= 0; i--) {
  const d = dv.date("today") - dv.duration(`${i} days`);
  const count = dv.pages('"AI-News"')
    .where(p => p.date >= d && p.date < d + dv.duration("1 day")).length;
  days.push([d.toFormat("MM-dd"), count]);
}
dv.table(["日期", "文章数"], days);
```
```

### Trending.md - 当前热点

```markdown
# 🔥 当前热点

## 近 48 小时热点文章

```dataview
TABLE trend_score AS "趋势分", relevance AS "相关度",
      source_name AS "来源", category AS "分类",
      length(platforms) AS "平台数"
FROM "AI-News"
WHERE date >= date(today) - dur(2 days) AND is_trending = true
SORT trend_score DESC
LIMIT 20
```

## 跨平台热点 (3+ 平台命中)

```dataview
TABLE length(platforms) AS "平台数", trend_score AS "趋势分"
FROM "AI-News"
WHERE date >= date(today) - dur(7 days)
  AND length(platforms) >= 3
SORT length(platforms) DESC, trend_score DESC
```
```

### Reading-List.md - 未读列表

```markdown
# 📋 阅读列表

## 未读文章 (按评分排序)

```dataview
TABLE relevance AS "评分", category AS "分类",
      dateformat(date, "MM-dd") AS "日期"
FROM "AI-News"
WHERE status = "unread"
SORT relevance DESC, date DESC
LIMIT 50
```

## 本周未读热点

```dataview
LIST
FROM "AI-News"
WHERE status = "unread" AND is_trending = true
  AND date >= date(today) - dur(7 days)
SORT trend_score DESC
```
```

### People-Tracker.md - 人物追踪

```markdown
# 👥 AI 人物追踪

## 📈 活跃度 Top 20 (最近30天)

```dataview
TABLE length(rows) AS "文章数"
FROM "AI-News"
WHERE date >= date(today) - dur(30 days)
FLATTEN entities.people AS person
GROUP BY person
SORT length(rows) DESC
LIMIT 20
```

## 🆕 新发现 (本周首次出现)

```dataview
LIST
FROM "AI-News/Entities/People"
WHERE first_seen >= date(today) - dur(7 days)
SORT first_seen DESC
```
```

### Daily-Stats.md - 每日统计

```markdown
# 📊 每日统计 (2026-04-13)

## 来源分布

```dataviewjs
const pages = dv.pages('"AI-News"')
  .where(p => p.date >= dv.date("today") && p.status != "duplicate");
const bySource = {};
for (const p of pages) {
  bySource[p.source_name] = (bySource[p.source_name] || 0) + 1;
}
dv.table(["来源", "文章数", "占比"],
  Object.entries(bySource)
    .sort((a,b) => b[1] - a[1])
    .map(([k,v]) => [k, v, (v/pages.length*100).toFixed(1) + "%"])
);
```

## 分类分布

```dataview
TABLE length(rows) AS "数量", round(avg(rows.relevance), 1) AS "平均评分"
FROM "AI-News"
WHERE date >= date(today) AND status != "duplicate"
GROUP BY category
SORT length(rows) DESC
```
```

### Knowledge-Graph.md - 知识图谱

```markdown
# 🔗 知识图谱

Obsidian 原生 **Graph View** 自动生成知识图谱。
通过文章中的 `[[双链]]` 和 frontmatter 中的 `entities`，
实体页面和文章页面自动关联。

## 快捷入口

### 人物
```dataview
LIST
FROM "AI-News/Entities/People"
SORT mention_count DESC
LIMIT 30
```

### 公司/组织
```dataview
LIST
FROM "AI-News/Entities/Companies"
SORT mention_count DESC
LIMIT 20
```

### 项目/产品
```dataview
LIST
FROM "AI-News/Entities/Projects"
SORT mention_count DESC
LIMIT 20
```

> 打开 Obsidian Graph View 查看完整关联图。
```

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

## 知识图谱说明

Obsidian 的 **Graph View** 天然支持知识图谱：
- 每篇文章通过 `[[双链]]` 关联到实体页面
- 每个实体页面反向关联到所有提到它的文章
- 人物 → 公司 → 项目 → 技术 → 文章 形成完整关联网络
- 随文章增长，图谱自动扩展，无需额外维护

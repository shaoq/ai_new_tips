# 系统架构设计

## 整体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                        ainews CLI                                     │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐              │
│  │  数据采集层  │──▶│  智能处理层  │──▶│   输出分发层   │              │
│  │  (Fetcher)   │   │ (Processor)  │   │  (Publisher)  │              │
│  └─────────────┘   └─────────────┘   └──────────────┘              │
│         │                 │                   │                      │
│    ┌────┴────┐      ┌────┴────┐        ┌─────┴─────┐               │
│    │         │      │         │        │           │                │
│  RSS/API  X/推特   去重/分类  摘要    Obsidian   钉钉Webhook        │
│  免费     后续扩展  LLM驱动   LLM     REST API   即时通知           │
│                                                                      │
│                     ┌─────────────┐                                  │
│                     │  SQLite DB  │                                  │
│                     │  (本地存储)  │                                  │
│                     └─────────────┘                                  │
└──────────────────────────────────────────────────────────────────────┘
```

## 数据流

```
[采集]              [处理]                [存储]           [分发]
                                          ┌─────────┐
 HackerNews ──┐                          │         │
 ArXiv ───────┤                          │ SQLite  │
 Reddit ──────┼──▶ Fetch ──▶ Dedup ──────┤  (全量)  │──▶ Obsidian (全量归档)
 RSS Blogs ───┤    & Store   │           │         │    ├─ 分类归档
 HF Papers ───┤              │           └─────────┘    ├─ 每日笔记
 GitHub ──────┤              │                           ├─ 仪表盘
 中文源 ──────┘              │                           └─ 知识图谱
                    Classify ──▶ Categorize
                    Summarize──▶ Score Relevance         钉钉 (增量推送)
                    Enrich ────▶ Extract Tags             ├─ feedCard (晨晚报)
                    Trend ─────▶ Cross-source Correlate   ├─ actionCard (即时热点)
                                Entity Discovery           └─ markdown (周报)
```

## 模块划分

```
ainews/
├── cli/                    # CLI 命令入口
│   ├── main.py            # 主入口 (ainews)
│   ├── config.py          # config 子命令
│   ├── sources.py         # sources 子命令
│   ├── run.py             # run 子命令
│   ├── fetch.py           # fetch 子命令
│   ├── process.py         # process 子命令
│   ├── sync.py            # sync 子命令
│   ├── push.py            # push 子命令
│   ├── stats.py           # stats 子命令
│   ├── cron.py            # cron 子命令
│   └── db.py              # db 子命令
│
├── fetcher/                # 数据采集层
│   ├── base.py            # Fetcher 基类
│   ├── hackernews.py      # HackerNews API
│   ├── arxiv.py           # ArXiv API
│   ├── reddit.py          # Reddit API (PRAW)
│   ├── rss.py             # RSS/Atom feeds
│   ├── hf_papers.py       # HuggingFace Papers API
│   ├── github.py          # GitHub Trending
│   └── chinese.py         # 中文源 (量子位/机器之心等)
│
├── processor/              # 智能处理层
│   ├── dedup.py           # 去重 (URL + 内容指纹)
│   ├── classifier.py      # 分类 (LLM)
│   ├── summarizer.py      # 中文摘要 (LLM)
│   ├── scorer.py          # 相关性评分 (LLM)
│   ├── entity_extractor.py # 实体提取 (LLM)
│   ├── tagger.py          # 标签提取 (LLM)
│   └── trend.py           # 跨源关联 + 热点评分
│
├── publisher/              # 输出分发层
│   ├── obsidian.py        # Obsidian REST API 客户端
│   ├── dingtalk.py        # 钉钉 Webhook 客户端
│   └── formatter.py       # 消息格式化 (feedCard/markdown/actionCard)
│
├── storage/                # 存储层
│   ├── database.py        # SQLite 数据库管理
│   ├── models.py          # 数据模型 (SQLModel)
│   └── migrations.py      # 数据库迁移
│
├── llm/                    # LLM 抽象层
│   ├── client.py          # LLM 客户端 (Anthropic 协议)
│   ├── prompts.py         # Prompt 模板
│   └── config.py          # LLM 配置
│
├── scheduler/              # 定时任务
│   ├── launchd.py         # macOS launchd 管理
│   └── templates.py       # plist 模板
│
├── config/                 # 配置管理
│   ├── settings.py        # pydantic-settings 配置模型
│   └── schema.py          # 配置 Schema 定义
│
├── templates/              # Obsidian 模板
│   ├── article.md         # 文章模板
│   ├── daily.md           # 每日笔记模板
│   ├── entity.md          # 实体页面模板
│   └── dashboards/        # 仪表盘模板
│       ├── home.md
│       ├── trending.md
│       ├── daily-stats.md
│       ├── weekly-stats.md
│       ├── reading-list.md
│       ├── people-tracker.md
│       ├── knowledge-graph.md
│       └── by-category.md
│
└── utils/                  # 工具函数
    ├── url.py             # URL 标准化
    ├── text.py            # 文本处理 (相似度等)
    └── crypto.py          # 钉钉签名等
```

## 完整流水线 (ainews run)

```
ainews run 执行流程:

  Step 1: fetch
    ├─ 读取 fetch_log 获取每个源的上次拉取时间
    ├─ 并发拉取所有已启用源
    ├─ 存入 SQLite (URL 去重)
    └─ 更新 fetch_log cursor

  Step 2: process
    ├─ 筛选未处理的文章 (processed = false)
    ├─ 批量调用 LLM: 分类 + 摘要 + 评分 + 实体提取
    ├─ 更新文章的 category / summary_zh / relevance / entities
    └─ 标记 processed = true

  Step 3: dedup
    ├─ 内容指纹去重 (标题相似度 > 0.9)
    └─ 标记重复文章

  Step 4: trend
    ├─ 跨源关联: URL 标准化匹配
    ├─ 标题语义聚类
    ├─ 计算每个 cluster 的 trend_score
    ├─ 更新文章 is_trending 和 trend_score
    └─ 检测新实体，写入 entities 表

  Step 5: sync obsidian
    ├─ 检查 Obsidian REST API 连通性
    ├─ 写入新文章文件到分类文件夹
    ├─ 追加到 Daily 笔记 (## HH:MM 更新)
    ├─ 同步新实体页面
    └─ 仪表盘由 Dataview 自动更新

  Step 6: push dingtalk
    ├─ 筛选未推送的文章 (dingtalk_sent = false)
    ├─ 根据推送策略选择格式:
    │   ├─ 定时全量 → feedCard
    │   ├─ 仅热点 → actionCard (trend_score ≥ 8)
    │   └─ 周报 → markdown
    ├─ 发送钉钉 Webhook
    └─ 标记 dingtalk_sent = true
```

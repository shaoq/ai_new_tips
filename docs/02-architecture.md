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
[采集]              [处理]            [去重]        [趋势]           [分发]
                                                              ┌──────────────┐
 HackerNews ──┐                                          │   Obsidian    │
 ArXiv ───────┤    ┌────────────┐   ┌──────┐  ┌───────┐ │  REST API     │
 Reddit ──────┼───▶│   Process   │──▶│Dedup │─▶│ Trend │─▶│               │
 RSS Blogs ───┤    │  (LLM 驱动)  │   │ 标题  │  │ 跨源  │ │  ├─ 分类归档   │
 HF Papers ───┤    │             │   │相似度 │  │ 关联  │ │  ├─ 每日笔记   │
 GitHub ──────┤    │ • 分类       │   └──────┘  └───────┘ │  ├─ 仪表盘     │
 GitHub Rel.──┤    │ • 中文标题   │         │        │     │  └─ 实体页面   │
 Chinese ─────┤    │ • 摘要       │         ▼        ▼     └──────┬───────┘
 Twitter/X ───┘    │ • 评分       │     ┌──────────────┐          │
                   │ • 实体提取   │     │    SQLite    │          ▼
                   └────────────┘     │    (全量)     │   ┌──────────────┐
                         │             └──────────────┘   │   钉钉        │
                         ▼                                  │  Webhook     │
                    ┌────────────┐                          │               │
                    │   title_zh │                          │  ├─ feedCard  │
                    │  中文标题   │                          │  ├─ actionCard│
                    └────────────┘                          │  └─ markdown │
                                                           └──────────────┘
```

**核心流水线编排** (`pipeline/runner.py`):

```
PipelineRunner 按 Step 模式顺序执行:

  Fetch ──▶ Process ──▶ Dedup ──▶ Trend ──▶ Sync Obsidian ──▶ Push DingTalk
    │          │           │         │            │                  │
    │          │           │         │            └─ 可跳过 (--skip-sync)
    │          │           │         │                                │
    │          │           └─ 可跳过  └────────────────────────────────┘
    │          │                                                    └─ 可跳过 (--no-push)
    │          └─ 生成 title_zh + 进度反馈
    │
    └─ 进度反馈: 每步输出耗时 + 处理数量

  每个 Step:
    ▸ Step name...              ← 开始
         OK  Step name (1.2s, 42 items)  ← 完成并输出耗时/数量
     SKIPPED  Step name          ← 被跳过
     FAILED  Step name — error   ← 执行失败
```

## 模块划分

```
ainews/
├── cli/                    # CLI 命令入口
│   ├── main.py            # 主入口 (ainews)，注册所有子命令
│   ├── config.py          # config 子命令 — 查看/编辑配置
│   ├── sources.py         # sources 子命令 — 管理数据源
│   ├── run.py             # run 子命令 — 执行完整流水线
│   ├── fetch.py           # fetch 子命令 — 仅采集数据
│   ├── process.py         # process 子命令 — 仅 LLM 处理
│   ├── dedup.py           # dedup 子命令 — 标题相似度去重
│   ├── trend.py           # trend 子命令 — 趋势分析流水线
│   ├── entities.py        # entities 子命令 — 管理实体库
│   ├── sync.py            # sync 子命令 — 同步 Obsidian
│   ├── push.py            # push 子命令 — 推送钉钉
│   ├── stats.py           # stats 子命令 — 统计信息
│   ├── cron.py            # cron 子命令 — macOS launchd 定时任务
│   ├── db.py              # db 子命令 — 数据库管理
│   └── doctor.py          # doctor 子命令 — 环境检查
│
├── fetcher/                # 数据采集层
│   ├── base.py            # Fetcher 抽象基类，定义 fetch() 接口
│   ├── registry.py        # 采集器注册表，source_name → FetcherClass 映射
│   ├── runner.py          # 采集编排器，根据参数选择数据源并执行
│   ├── hackernews.py      # HackerNews API 采集
│   ├── arxiv.py           # ArXiv API 采集
│   ├── reddit.py          # Reddit API 采集
│   ├── rss.py             # RSS/Atom feeds 采集
│   ├── hf_papers.py       # HuggingFace Papers API 采集
│   ├── github.py          # GitHub Trending 采集
│   ├── github_releases.py # GitHub Releases 采集，监控仓库版本发布
│   ├── chinese.py         # 中文源采集 (量子位/机器之心等)
│   └── twitter.py         # Twitter/X 采集 (SocialData.tools API)
│
├── processor/              # 智能处理层
│   ├── processor.py       # 文章处理管线，调用 LLM 做分类/摘要/评分/实体提取
│   └── entity_handler.py  # 实体入库处理，实体查找/创建/mention_count 递增
│
├── trend/                  # 趋势分析层
│   ├── url_normalizer.py  # URL 标准化与 hash 计算
│   ├── title_cluster.py   # 标题语义聚类 (SequenceMatcher 相似度)
│   ├── scorer.py          # 综合趋势评分，多维度加权计算 trend_score
│   ├── hotness.py         # 单源热度算法，各平台排名/热度计算与归一化
│   ├── correlator.py      # 跨源关联引擎，整合 URL 匹配和标题聚类
│   ├── dedup.py           # 文章去重，基于标题相似度检测重复
│   ├── entity_discovery.py # 实体发现引擎，从 LLM 提取结果中发现和追踪实体
│   └── auto_discover.py   # 自动发现机制，新兴研究员/项目/公司
│
├── pipeline/               # 流水线编排
│   └── runner.py          # 流水线编排引擎，Step 模式执行 fetch→process→dedup→trend→sync→push
│
├── publisher/              # 输出分发层
│   ├── obsidian_client.py # Obsidian Local REST API 客户端
│   ├── article_sync.py    # 文章同步到 Obsidian Vault
│   ├── daily_note.py      # 每日笔记同步到 Obsidian
│   ├── dashboards.py      # 仪表盘初始化，创建 5 个 Bases 仪表盘模板
│   ├── entity_pages.py    # 实体页面同步到 Obsidian Vault
│   ├── formatter.py       # 消息格式化 (feedCard/markdown/actionCard)
│   ├── obsidian_templates.py # Obsidian Markdown 模板渲染
│   ├── strategy.py        # 推送策略引擎，去重/每日上限/文章查询
│   └── dingtalk.py        # 钉钉 Webhook 客户端
│
├── storage/                # 存储层
│   ├── database.py        # SQLite 数据库管理，连接/初始化/会话
│   ├── models.py          # 数据模型 (SQLModel: Article, Entity, Cluster 等)
│   └── crud.py            # CRUD 操作辅助函数 (get_or_create 等)
│
├── llm/                    # LLM 抽象层
│   ├── client.py          # LLM 客户端 (Anthropic 协议，支持 OpenAI 兼容接口)
│   └── prompts.py         # Prompt 模板 (合并处理提示词等)
│
├── scheduler/              # 定时任务
│   ├── launchd.py         # macOS launchd 管理
│   └── templates.py       # plist 模板
│
├── config/                 # 配置管理
│   ├── settings.py        # pydantic-settings 配置模型 (AppConfig)
│   └── loader.py          # 配置文件读写，YAML 加载/保存
│
├── templates/              # Obsidian 模板
│   └── __init__.py        # 模板包 (Markdown 模板由 publisher/obsidian_templates.py 渲染)
│
└── utils/                  # 工具函数
    └── logging.py          # 日志系统，按日归档 + latest.log 软链接
```

## 完整流水线 (ainews run)

由 `pipeline/runner.py` 的 `PipelineRunner` 编排，支持 `--dry-run`、`--skip-sync`、`--no-push`、`--trending-only-push` 等选项。

每步执行时输出进度: 开始显示 `▸ Step name...`，完成后显示状态（OK / SKIPPED / FAILED）、耗时和处理数量。最终输出汇总表 (`Pipeline Summary`)。

```
ainews run 执行流程:

  Step 1: Fetch
    ├─ FetcherRunner 根据参数选择数据源
    ├─ 通过 Registry 查找并执行各源 Fetcher
    ├─ 存入 SQLite (URL 去重)
    ├─ 输出进度: OK  Fetch (3.5s, 28 items)
    └─ 返回采集文章总数

  Step 2: Process
    ├─ 筛选未处理的文章 (processed = false)
    ├─ 调用 LLM 合并处理: 分类 + 中文标题(title_zh) + 摘要 + 评分 + 实体提取
    ├─ EntityHandler 处理实体入库 (查找/创建/mention_count 递增)
    ├─ 更新文章的 title_zh / category / summary_zh / relevance / entities
    ├─ 标记 processed = true
    ├─ 输出进度: OK  Process (12.1s, 15 items)
    └─ 支持 --limit 限制处理数量、backfill_title_zh 回填

  Step 3: Dedup
    ├─ 基于标题相似度 (SequenceMatcher > 0.9) 检测重复
    ├─ 标记重复文章
    ├─ 输出进度: OK  Dedup (0.8s, 3 items)
    └─ 可通过 --days 控制扫描范围

  Step 4: Trend
    ├─ URL 标准化匹配，跨源关联相同话题
    ├─ 标题语义聚类 (相似度 > 0.8)
    ├─ 多维度加权计算 trend_score (平台热度 + 跨源 + 速度)
    ├─ 更新文章 is_trending 和 trend_score
    ├─ 实体发现: 从 LLM 提取结果中发现和追踪实体
    ├─ 输出进度: OK  Trend (2.3s, 5 items)
    └─ 自动发现: 新兴研究员/项目/公司

  Step 5: Sync Obsidian
    ├─ ObsidianClient 通过 Local REST API 写入
    ├─ article_sync: 写入新文章到分类文件夹
    ├─ daily_note: 追加到每日笔记 (## HH:MM 更新)
    ├─ entity_pages: 同步新实体页面
    ├─ dashboards: 仪表盘由 Dataview/Bases 自动更新
    ├─ 输出进度: OK  Sync Obsidian (5.2s, 12 items)
    └─ 可通过 --skip-sync 跳过

  Step 6: Push DingTalk
    ├─ PushStrategy 查询待推送文章 (去重 + 每日上限)
    ├─ 根据推送策略选择格式:
    │   ├─ 定时全量 (query_morning_articles) → feedCard
    │   └─ 仅热点 (query_trending_articles) → feedCard
    ├─ DingTalkClient 发送 Webhook
    ├─ 输出进度: OK  Push DingTalk (0.5s, 8 items)
    └─ 可通过 --no-push 跳过、--trending-only-push 仅推送热点
```

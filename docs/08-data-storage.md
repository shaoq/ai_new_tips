# 数据存储与增量机制

## SQLite 数据库

### 为什么选择 SQLite

| 特性 | SQLite | PostgreSQL |
|------|--------|-----------|
| 部署 | 零配置，单文件 | 需要服务进程 |
| 适合场景 | 单用户 CLI 工具 | 多用户 Web 应用 |
| 本项目 | ✅ 完美匹配 | 过度设计 |
| 性能 | 本地读写极快 | 网络开销 |
| 备份 | 复制文件即可 | 需要导出 |

数据库文件位置: `~/.ainews/data.db`

### 表结构

```sql
-- 文章表
CREATE TABLE articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,        -- 原文 URL (唯一约束)
    url_hash        TEXT NOT NULL,               -- URL SHA256 (快速查找)
    title           TEXT NOT NULL,
    content_raw     TEXT,                        -- 原始内容 (HTML/Markdown)
    source          TEXT NOT NULL,               -- 来源类型: hackernews/arxiv/reddit/rss/hf_papers/github/chinese
    source_name     TEXT,                        -- 来源名称: OpenAI Blog / HackerNews
    author          TEXT,                        -- 原始作者

    -- LLM 处理结果
    category        TEXT,                        -- 分类: industry/research/tools/safety/policy
    summary_zh      TEXT,                        -- 中文摘要
    relevance       REAL,                        -- 相关性评分 1-10
    tags            TEXT,                        -- JSON array: ["ai", "llm"]
    entities        TEXT,                        -- JSON object: {people:[], companies:[], projects:[], tech:[]}

    -- 热点相关
    trend_score     REAL DEFAULT 0,              -- 热点评分 0-10
    is_trending     BOOLEAN DEFAULT FALSE,       -- 是否热点
    platforms       TEXT,                        -- JSON array: ["hackernews", "reddit"]

    -- 状态管理
    status          TEXT DEFAULT 'unread',       -- unread/reading/read/duplicate
    processed       BOOLEAN DEFAULT FALSE,       -- 是否已 LLM 处理
    dingtalk_sent   BOOLEAN DEFAULT FALSE,       -- 是否已推送钉钉
    obsidian_synced BOOLEAN DEFAULT FALSE,       -- 是否已同步 Obsidian

    -- 时间戳
    published_at    TIMESTAMP,                   -- 文章发布时间
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imported_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    obsidian_path   TEXT                         -- Obsidian 文件路径
);

CREATE INDEX idx_articles_url_hash ON articles(url_hash);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_articles_trend_score ON articles(trend_score DESC);
CREATE INDEX idx_articles_fetched_at ON articles(fetched_at);
CREATE INDEX idx_articles_status ON articles(status);

-- 单源热度指标
CREATE TABLE source_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id      INTEGER NOT NULL REFERENCES articles(id),
    source          TEXT NOT NULL,               -- 哪个平台的指标
    platform_score  REAL,                        -- 平台分数 (HN points / Reddit upvotes)
    comment_count   INTEGER DEFAULT 0,
    upvote_count    INTEGER DEFAULT 0,
    velocity        REAL DEFAULT 0,              -- 增长速度 (分/小时)
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_source_metrics_article ON source_metrics(article_id);

-- 拉取日志 (增量水印)
CREATE TABLE fetch_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT UNIQUE NOT NULL,         -- 源标识
    last_fetch_at   TIMESTAMP,                   -- 上次拉取时间
    cursor          TEXT,                         -- 源特定的游标 (since_id / ETag 等)
    items_fetched   INTEGER DEFAULT 0,            -- 本次拉取条数
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 实体库
CREATE TABLE entities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    type            TEXT NOT NULL,                -- person/company/project/technology
    first_seen_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mention_count   INTEGER DEFAULT 0,
    is_new          BOOLEAN DEFAULT TRUE,         -- 首次发现标记
    metadata        TEXT                          -- JSON: 额外信息 (URL/简介等)
);

CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_name ON entities(name);

-- 文章-实体关联
CREATE TABLE article_entities (
    article_id      INTEGER NOT NULL REFERENCES articles(id),
    entity_id       INTEGER NOT NULL REFERENCES entities(id),
    PRIMARY KEY (article_id, entity_id)
);

-- 跨源聚类
CREATE TABLE clusters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic           TEXT,                         -- 聚类主题描述
    article_ids     TEXT NOT NULL,                -- JSON array of article IDs
    source_count    INTEGER DEFAULT 0,            -- 涉及平台数
    trend_score     REAL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 推送日志
CREATE TABLE push_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id      INTEGER REFERENCES articles(id),
    push_type       TEXT NOT NULL,                -- feedcard/actioncard/markdown/weekly
    msg_id          TEXT,                         -- 钉钉消息 ID
    pushed_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 增量机制

### 首次运行 vs 后续运行

```
首次运行 (--backfill 7d):
┌──────────────────────────────────────────────────────┐
│  HackerNews:  Algolia 搜索最近 7 天 points>10        │
│  ArXiv:       submittedDate >= now-7d                │
│  RSS:         拉取最近 7 天的条目 (RSS 自带时间戳)    │
│  Reddit:      /new?t=week                            │
│  HF Papers:   /api/daily_papers?date=now-7d..now     │
│  GitHub:      7天内创建的 stars>100 仓库              │
│  中文源:      最近 7 天文章                            │
└──────────────────────────────────────────────────────┘

后续运行 (增量):
┌──────────────────────────────────────────────────────┐
│  读取 fetch_log 获取每个源的上次拉取时间/游标          │
│  只拉取 last_fetch 之后的新内容                       │
│  更新 fetch_log.cursor                              │
└──────────────────────────────────────────────────────┘
```

### 各源水印策略

| 源 | 水印方式 | cursor 字段 |
|----|---------|------------|
| HackerNews | 基于时间戳 | `last_item_timestamp` |
| ArXiv | submittedDate 过滤 | `last_submit_date` |
| RSS | HTTP ETag / Last-Modified 头 | `etag` + `last_modified` |
| Reddit | 基于时间戳 | `last_post_timestamp` |
| HF Papers | 基于日期 | `last_date` |
| GitHub | 基于创建时间 | `last_created_at` |
| 中文源 | 基于时间戳 | `last_item_timestamp` |

### 处理批次限制

process 步骤每次运行默认最多处理 50 篇未处理文章（`DEFAULT_BATCH_LIMIT=50`），
可通过 `--limit` 参数配置。如果未处理文章数超过 50，需要多次运行或使用
`ainews process --limit 0`（0 表示不限制）来处理全部。

### 去重机制

```
双重去重:

  Layer 1: URL 去重 (精确匹配)
    ├─ URL → SHA256 hash
    ├─ articles.url UNIQUE 约束
    └─ 同一 URL 绝对不会重复入库
    注意: 实现采用逐条检查+写入（check+flush）而非批量 INSERT，
         以避免 UNIQUE 约束冲突导致整个批次失败

  Layer 2: 内容指纹去重 (模糊匹配)
    ├─ 标题相似度计算 (SequenceMatcher / sentence-transformers)
    ├─ 相似度 > 0.9 → 标记为 duplicate
    └─ 保留最早入库的那篇，后续的标记 status = "duplicate"
```

### 增量更新已有文章

```
同一篇文章被多个源报道时:

  Run 1: HN 发现 → 创建文章
    trend_score: 7.0, platforms: ["hackernews"]
    source_metrics: [{source: "hn", score: 342}]

  Run 2: Reddit + RSS 也报道 → 更新已有文章
    trend_score: 8.7 (重新计算)
    platforms: ["hackernews", "reddit", "rss"]
    source_metrics 新增: [{source: "reddit", score: 1200}, ...]

  处理逻辑:
    ├─ URL 匹配 → 文章已存在
    ├─ 不创建新文件
    ├─ 更新 frontmatter: trend_score, platforms
    ├─ source_metrics 表新增记录
    └─ 钉钉: trend_score 大幅上升 → 可能触发即时推送
```

## 数据清理

```bash
# 清理 90 天前的旧数据
ainews db cleanup --days 90

# 清理逻辑:
#   ├─ articles: 删除 fetched_at < 90天前 的记录
#   ├─ source_metrics: 级联删除
#   ├─ clusters: 删除 created_at < 90天前
#   ├─ push_log: 删除 pushed_at < 90天前
#   ├─ entities: 保留 (mention_count > 0 的不删除)
#   └─ fetch_log: 保留 (需要维持增量水印)
```

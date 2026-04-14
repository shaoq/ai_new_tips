# 数据源详细分析

## 优先级分层

| 优先级 | 来源 | 成本 | 信号质量 | 接入方式 | 热点信号 |
|-------|------|------|---------|---------|---------|
| **P0** | HackerNews API | 免费 | 极高 | REST API，无需认证 | score + velocity |
| **P0** | ArXiv API | 免费 | 极高 | REST API，无需认证 | 引用速度 (via Semantic Scholar) |
| **P0** | AI Blog RSS | 免费 | 高 | feedparser | 跨源出现 |
| **P1** | Reddit | 免费 | 高 | PRAW (OAuth) | score + comments |
| **P1** | HuggingFace Papers | 免费 | 高 | REST API，无需认证 | upvotes |
| **P1** | GitHub Trending | 免费 | 高 | REST API / 爬取 | stars velocity |
| **P2** | 中文源 | 免费 | 中高 | RSS + 网页解析 | 跨源关联 |
| **P3** | X/Twitter | 按量付费 | 高 | X API v2 (后续扩展) | — |

## P0: HackerNews

### 接入方式

两个互补 API：

| API | 用途 | Base URL |
|-----|------|----------|
| Firebase API | 实时数据、当前排名、轮询 | `https://hacker-news.firebaseio.com/v0/` |
| Algolia Search API | 历史搜索、过滤、日期范围 | `http://hn.algolia.com/api/v1/search` |

### 关键端点

```
Firebase:
  GET /topstories.json        → 当前首页 (最多500个ID)
  GET /newstories.json        → 最新提交
  GET /beststories.json       → 最佳故事
  GET /item/{id}.json         → 单条详情 (score, kids, url, title, time)

Algolia (带过滤):
  GET /search?query=AI&tags=story&numericFilters=points>50,created_at_i>1712966400
```

### AI 关键词过滤

```python
AI_KEYWORDS = [
    "AI", "artificial intelligence", "LLM", "GPT", "Claude", "Gemini",
    "machine learning", "deep learning", "neural network", "transformer",
    "diffusion", "AGI", "ChatGPT", "OpenAI", "Anthropic", "DeepMind",
    "computer vision", "NLP", "generative", "embedding", "fine-tuning",
    "RAG", "agent", "MCP", "reasoning", "multimodal"
]
```

### 速率限制

无正式限制，社区约定 ~1 请求/秒。

---

## P0: ArXiv

### 接入方式

- **端点**: `https://export.arxiv.org/api/query`
- **格式**: Atom 1.0 XML
- **速率**: 1 请求/3 秒
- **认证**: 不需要
- **注意**: HTTP 客户端使用 `follow_redirects=True`，以正确处理 ArXiv 的重定向行为

### 监控分类

```
cs.AI  - Artificial Intelligence
cs.LG  - Machine Learning
cs.CL  - Computation and Language (NLP)
cs.CV  - Computer Vision
stat.ML - Machine Learning (Statistics)
```

### 查询示例

```
https://export.arxiv.org/api/query?
  search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL
  &sortBy=submittedDate
  &sortOrder=descending
  &start=0
  &max_results=50
```

### Python 库

```bash
pip install arxiv
```

---

## P0: AI Blog RSS

### 核心订阅源

| 源 | RSS URL | 内容类型 |
|----|---------|---------|
| OpenAI Blog | `https://openai.com/blog/rss.xml` | 产品发布、研究 |
| Google DeepMind | `https://deepmind.google/blog/rss/` | 研究突破 |
| Hugging Face Blog | `https://huggingface.co/blog/feed.xml` | 开源 ML、模型发布 |
| MarkTechPost | `https://www.marktechpost.com/feed/` | AI 研究日报 |
| MIT Tech Review AI | `https://www.technologyreview.com/feed/topic/artificial-intelligence/` | 深度报道 |
| VentureBeat AI | `https://venturebeat.com/category/ai/feed/` | 产业新闻 |
| The Gradient | `https://thegradient.pub/rss/` | 研究视角 |
| BAIR Blog | `https://bair.berkeley.edu/blog/index.xml` | 学术研究 |
| Reddit r/MachineLearning | `https://www.reddit.com/r/MachineLearning/.rss` | 技术研究、论文讨论 |
| Reddit r/LocalLLaMA | `https://www.reddit.com/r/LocalLLaMA/.rss` | 本地模型、开源 LLM |
| Reddit r/ChatGPT | `https://www.reddit.com/r/ChatGPT/.rss` | ChatGPT 新闻和讨论 |

### RSS 解析

```bash
pip install feedparser httpx
```

增量机制：使用 HTTP `ETag` / `Last-Modified` 头，仅获取新内容。

**HTTP 获取方式**: Fetcher 现在使用 httpx 进行 HTTP 请求，再将响应传递给 feedparser 解析。相比直接使用 feedparser 的内置 HTTP 客户端，httpx 对重定向、自定义请求头等场景的处理更为健壮。

**条目数量限制**: 每个 feed 最多处理 `MAX_ENTRIES_PER_FEED=30` 条条目，避免在单次采集中拉取过多历史数据。

---

## P1: Reddit

### 接入方式

- **认证**: OAuth2，在 reddit.com/prefs/apps 注册应用
- **免费额度**: 100 查询/分钟（个人使用足够）
- **Python 库**: PRAW (`pip install praw`)

### 监控 Subreddit

| Subreddit | 成员数 | 关注点 |
|-----------|-------|-------|
| r/MachineLearning | ~3M | 技术研究、论文讨论 |
| r/LocalLLaMA | 活跃 | 本地模型、开源 LLM |
| r/ChatGPT | ~9.9M | ChatGPT 新闻和讨论 |

### 配置示例

```yaml
reddit:
  client_id: "xxx"
  client_secret: "xxx"
  user_agent: "ai-news-tips/1.0"
  subreddits:
    - MachineLearning
    - LocalLLaMA
    - ChatGPT
```

---

## P1: HuggingFace Daily Papers

### 接入方式

- **端点**: `https://huggingface.co/api/daily_papers`
- **认证**: 不需要
- **成本**: 免费

### 关键端点

```
GET /api/daily_papers?date=2026-04-14&limit=50    → 每日精选论文
GET /api/papers/{arxiv_id}                         → 论文详情
GET /api/papers/search?q=transformer               → 搜索论文
```

### 热点信号

- upvotes 数：100+ = 强热点，50+ = 值得关注
- 每天约 20-50 篇精选论文

---

## P1: GitHub Trending

### 接入方式

| 方式 | URL | 说明 |
|------|-----|------|
| GitHub Search API | `https://api.github.com/search/repositories?q=created:>2026-04-07+stars:>100&sort=stars` | 官方，有速率限制 |
| OSSInsight API | `https://ossinsight.io/docs/api/list-trending-repos` | 趋势数据 |
| 非官方 API | `https://github.com/huchenme/github-trending-api` | 爬取 GitHub Trending 页 |

### AI 关键词

```
topics: machine-learning, deep-learning, llm, gpt, ai, transformer,
        stable-diffusion, langchain, rag, ai-agent, mcp
language: python, typescript, rust
```

---

## P2: 中文源

### 核心源

| 源 | URL | 获取方式 |
|----|-----|---------|
| 量子位 (QbitAI) | https://www.qbitai.com/ | RSS / 网页解析 |
| 机器之心 (Jiqizhixin) | https://www.jiqizhixin.com/ | RSS / 网页解析 |
| AIbase | https://www.aibase.com/ | 网页解析 |
| 新智元 | 36Kr 专栏 | RSS |

### 说明

中文源作为辅助，重点英文源。中文 RSS 质量参差不齐，可能需要网页解析兜底。

---

## P3: X/Twitter (后续扩展)

### 免费替代方案

| 方案 | 成本 | 可靠性 | 说明 |
|------|------|-------|------|
| **TwitterAPI.io** | 100K 免费注册额度 | 高 | 发现：拉取用户时间线 ID |
| **cdn.syndication.twimg.com** | 免费 | 高 | 富化：已知 ID 获取完整 JSON |
| **Apify 免费额度** | $5/月免费 | 中 | 预构建 Twitter Scraper Actor |
| **Inoreader 免费版** | 免费 | 中 | RSS 方式监控 X 账户 |

### 推荐策略

1. 用 TwitterAPI.io (免费额度) 拉取关注列表时间线，获取 tweet ID
2. 用 `cdn.syndication.twimg.com/tweet-result?id={ID}&token=random` 获取完整 JSON（免费、无需认证、无已知速率限制）
3. 额度用完后可切到 Apify ($5/月免费额度)

### 建议关注的 AI 人物

**研究者:**
- @karpathy - Andrej Karpathy
- @ylecun - Yann LeCun
- @AndrewYNg - Andrew Ng
- @rasbt - Sebastian Raschka
- @ilyasut - Ilya Sutskever

**创始人/CEO:**
- @sama - Sam Altman (OpenAI)
- @demishassabis - Demis Hassabis (DeepMind)
- @ClementDelangue - Clément Delangue (Hugging Face)
- @arthur_mensch - Arthur Mensch (Mistral AI)

**评论/新闻:**
- @GaryMarcus - Gary Marcus (AI 批评家)
- @emollick - Ethan Mollick (实用 AI)
- @CadeMetz - Cade Metz (NYT AI 记者)
- @mattturck - Matt Turck (AI 产业地图)

**官方:**
- @OpenAI, @DeepMind, @AnthropicAI, @huggingface, @dair_ai

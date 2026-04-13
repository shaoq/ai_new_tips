# 热点感知与自动发现

## 设计目标

不依赖 X/Twitter，通过多源信号叠加实现热点感知和自动发现能力：
- 感知热点文章（什么样的文章正在爆发）
- 自动发现新的 AI 研究员、公司、项目、技术

## 三层热点检测架构

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Layer 1: 单源热度 (每个平台自己的排名算法)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ HN Score │  │ Reddit   │  │ HF Papers│  │ GitHub   │      │
│  │ 排名算法  │  │ Hot 排名  │  │ Upvotes │  │ Stars    │      │
│  │ + 速度   │  │ + 评论数  │  │ (每日精选)│  │ + 速度   │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │              │              │              │            │
│  Layer 2: 跨源关联 (同一话题出现在多个平台 = 真热点)             │
│       └──────────┬───┴──────────┬───┘              │            │
│                  │   URL 去重    │                  │            │
│                  │   标题聚类    │                  │            │
│                  └──────┬───────┘                  │            │
│                         │                          │            │
│  Layer 3: LLM 增强 (提取人名/公司/项目 = 自动发现)              │
│                         │                          │            │
│                  ┌──────▼───────┐                  │            │
│                  │ 实体提取      │                  │            │
│                  │ 新实体检测    │◀─────────────────┘            │
│                  │ 话题聚类      │                               │
│                  └──────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

## Layer 1: 单源热度算法

### HackerNews 排名算法

```python
def calculate_hn_score(votes: int, item_hour_age: float, gravity: float = 1.8) -> float:
    """
    HN 官方排名算法 (来自 news.arc 源码)
    gravity 控制时间衰减速度，默认 1.8
    """
    return (votes - 1) / pow((item_hour_age + 2), gravity)
```

**热度阈值（经验值）:**

| 信号 | 普通 | 热点 | 爆款 |
|------|------|------|------|
| Score (1小时) | < 10 | 10-50 | > 50 |
| Score (6小时) | < 30 | 30-200 | > 200 |
| 评论数 | < 20 | 20-100 | > 100 |
| 速度 (分/首小时) | < 0.3 | 0.3-1.5 | > 1.5 |
| 首页位置 | > 60 | 10-60 | Top 10 |

### Reddit 排名算法

```python
from math import log

def reddit_hot(ups: int, downs: int, date_timestamp: float) -> float:
    """
    Reddit 官方 Hot 排名算法
    对数缩放：前 10 票 = 后 100 票 = 后 1000 票
    时间衰减：每 12.5 小时降一个单位
    """
    score = ups - downs
    order = log(max(abs(score), 1), 10)
    sign = 1 if score > 0 else -1 if score < 0 else 0
    seconds = date_timestamp - 1134028003
    return round(sign * order + seconds / 45000, 7)
```

**阈值:**

| 信号 | 普通 | 热点 |
|------|------|------|
| Score (6小时) | < 50 | > 100 |
| upvote_ratio | < 0.85 | > 0.90 |
| num_comments | < 30 | > 50 |
| score/hour (前6h) | < 10 | > 20 |

### HuggingFace Papers 热度

- Upvotes > 100 = 强热点
- Upvotes > 50 = 值得关注

### GitHub Stars 速度

- 一周内新增 500+ stars = 热门项目

## Layer 2: 跨源关联

### URL 去重

```python
from urllib.parse import urlparse

def normalize_url(url: str) -> str:
    """URL 标准化，用于跨源匹配"""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    # 移除 tracking 参数、fragment 等
    return f"{domain}{path}"
```

### 标题语义聚类

```python
def title_similarity(t1: str, t2: str) -> float:
    """标题相似度。生产环境可用 sentence-transformers 替代"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()
```

### 跨源关联示例

```
同一篇文章:

  HackerNews:  "OpenAI releases GPT-6"  (score: 842, 324 comments)
       │           URL: openai.com/blog/gpt-6
  Reddit:      "GPT-6 is here!"         (score: 1.2k, r/ChatGPT)
       │           URL: openai.com/blog/gpt-6
  RSS:         OpenAI Blog 新文章         (直接源)
       │           URL: openai.com/blog/gpt-6
       ▼
  关联成功! 3个平台命中 → trend_score 大幅提升 → 标记 is_trending
```

## Layer 3: LLM 实体提取

### Prompt 设计

```
从以下文章中提取所有命名实体，返回 JSON:
{
    "people": ["人名列表 (研究员、创始人、高管)"],
    "companies": ["公司/组织名列表"],
    "projects": ["项目/产品/模型名列表"],
    "technologies": ["具体技术名称列表"]
}

文章内容:
{article_text}

只返回有效 JSON，不要其他文本。
```

### 新实体检测逻辑

```python
def detect_new_entities(extracted: dict, known_entities: set) -> dict:
    """对比已知实体库，检测新实体"""
    new_entities = {}
    for category, entities in extracted.items():
        new_in_category = [e for e in entities if e.lower() not in known_entities]
        if new_in_category:
            new_entities[category] = new_in_category
    return new_entities
```

## 综合热点评分算法

```python
def calculate_trend_score(
    platform_hotness: float,      # 单源热度 (0-1 归一化)
    source_count: int,            # 出现平台数
    velocity: float,              # 增长速度
    entity_novelty: bool,         # 是否涉及新实体
) -> float:
    """
    综合热点评分 (0-10)
    """
    cross_platform_bonus = source_count ** 1.5
    novelty_bonus = 1.2 if entity_novelty else 1.0

    score = (
        platform_hotness * 0.35
        + min(cross_platform_bonus / 5, 1.0) * 0.35
        + min(velocity / 2.0, 1.0) * 0.20
    ) * novelty_bonus * 10

    return round(min(score, 10.0), 1)
```

**评分含义:**

| 分数 | 含义 | 推送策略 |
|------|------|---------|
| 0-4 | 低关注度 | 仅存入 Obsidian |
| 4-6 | 普通 | 存入 + 日报汇总 |
| 6-8 | 值得关注 | 存入 + 日报 + 标记热点 |
| 8-10 | 重大热点 | 存入 + 即时推送 actionCard + 日报 |

## 自动发现机制

### 发现新兴研究员

```
数据源: ArXiv + Semantic Scholar API
方法:
  1. 追踪近期 AI 论文作者
  2. 计算引用加速度: recent_citations / total_citations
  3. 满足条件 → 标记 "emerging_researcher"
     - 3 个月内发表 3+ 篇论文
     - 平均引用 > 5
     - 引用加速度 > 2x
```

### 发现新 AI 项目

```
数据源: HackerNews "Show HN" + GitHub Trending
方法:
  1. HN: 筛选 Show HN 帖子中的 AI 关键词，points > 50
  2. GitHub: 新仓库一周获 500+ stars
  3. 交叉验证: 同一项目在 HN + GitHub 同时出现 → 确认
```

### 发现新公司/组织

```
数据源: LLM 实体提取 + 跨文章关联
方法:
  1. 从文章中提取 company 实体
  2. 与已知公司库对比
  3. 首次出现的公司 → 标记 "new_company"
  4. 后续追踪其出现频率和关联文章
```

## Semantic Scholar API

```
端点: https://api.semanticscholar.org/graph/v1/
免费额度: 每5分钟1000次请求

关键端点:
  GET /paper/search?query=machine+learning&year=2026
  GET /paper/ArXiv:{id}?fields=citationCount,authors
  GET /paper/ArXiv:{id}/citations?fields=publicationDate
  GET /author/{id}?fields=name,paperCount,citationCount,hIndex
```

# 热点感知与自动发现

## 设计目标

不依赖 X/Twitter，通过多源信号叠加实现热点感知和自动发现能力：
- 感知热点文章（什么样的文章正在爆发）
- 自动发现新的 AI 研究员、公司、项目、技术

## 三层热点检测架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Layer 1: 单源热度 (trend/hotness.py — 各平台排名算法)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ HN Score │  │ Reddit   │  │ HF Papers│  │ GitHub   │          │
│  │ gravity  │  │ Hot 排名  │  │ Upvotes │  │ Stars    │          │
│  │ + 速度   │  │ + 评论数  │  │ (每日精选)│  │ + 速度   │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │              │                │
│  Layer 2: 跨源关联 (trend/correlator.py — 同一话题出现在多平台)    │
│       └──────────┬───┴──────────┬───┘              │                │
│                  │              │                  │                │
│  trend/url_normalizer.py        │                  │                │
│  trend/title_cluster.py         │                  │                │
│  trend/dedup.py                 │                  │                │
│                  └──────┬───────┘                  │                │
│                         │                          │                │
│  Layer 3: LLM 增强 (trend/entity_discovery.py + auto_discover.py)  │
│                         │                          │                │
│                  ┌──────▼───────┐                  │                │
│                  │ 实体提取      │                  │                │
│                  │ 新实体检测    │◀─────────────────┘                │
│                  │ 自动发现      │                                   │
│                  └──────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## 模块结构

```
ainews/trend/
├── url_normalizer.py   # URL 标准化与 hash 计算
├── title_cluster.py    # 标题语义聚类 (SequenceMatcher)
├── hotness.py          # 单源热度算法 (各平台排名 + sigmoid 归一化)
├── scorer.py           # 综合趋势评分 (多维度加权)
├── correlator.py       # 跨源关联引擎 (URL 匹配 + 标题聚类)
├── dedup.py            # 内容指纹去重 (标题相似度 > 0.9)
├── entity_discovery.py # 实体发现引擎 (从 LLM 结果中提取实体)
└── auto_discover.py    # 自动发现机制 (新兴研究员/项目/公司)
```

## Layer 1: 单源热度算法

实现于 `trend/hotness.py`，使用 sigmoid 归一化将各平台分数映射到 [0, 1]。

### HackerNews 排名算法

```python
def calculate_hn_score(points, comment_count, hours_ago, gravity=1.8):
    """HN 排名: (points + comments * 0.5) / (hours_ago + 2) ^ gravity"""
    return (points + comment_count * 0.5) / pow(hours_ago + 2, gravity)
```

归一化: `sigmoid_normalize(raw_score, midpoint=10.0, steepness=0.15)`

**热度阈值（经验值）:**

| 信号 | 普通 | 热点 | 爆款 |
|------|------|------|------|
| Score (1小时) | < 10 | 10-50 | > 50 |
| Score (6小时) | < 30 | 30-200 | > 200 |
| 评论数 | < 20 | 20-100 | > 100 |
| 速度 (分/首小时) | < 0.3 | 0.3-1.5 | > 1.5 |
| 首页位置 | > 60 | 10-60 | Top 10 |

### Reddit 排名算法

归一化: `sigmoid_normalize(raw_score, midpoint=80.0, steepness=0.2)`

**阈值:**

| 信号 | 普通 | 热点 |
|------|------|------|
| Score (6小时) | < 50 | > 100 |
| upvote_ratio | < 0.85 | > 0.90 |
| num_comments | < 30 | > 50 |
| score/hour (前6h) | < 10 | > 20 |

### HuggingFace Papers 热度

归一化: `sigmoid_normalize(raw_score, midpoint=20.0, steepness=0.15)`

- Upvotes > 100 = 强热点
- Upvotes > 50 = 值得关注

### GitHub Stars 速度

归一化: `sigmoid_normalize(raw_score, midpoint=50.0, steepness=0.1)`

- 一周内新增 500+ stars = 热门项目

## Layer 2: 跨源关联

### URL 标准化 (`trend/url_normalizer.py`)

```python
def normalize_url(url: str) -> str:
    """标准化 URL:
    1. 移除 scheme (http/https 差异)
    2. 移除 www 前缀
    3. 移除 tracking 参数 (utm_*, fbclid, gclid 等)
    4. 排序剩余查询参数
    5. 移除 trailing slash
    6. 转小写 hostname
    7. 移除 fragment (#锚点)
    """
```

### 标题语义聚类 (`trend/title_cluster.py`)

```python
def title_similarity(title_a: str, title_b: str) -> float:
    """使用 SequenceMatcher 计算最长公共子序列比率。返回 [0.0, 1.0]"""

def cluster_titles(session, days=1, threshold=0.8):
    """对指定天数的文章执行标题聚类，返回 Cluster 列表"""
```

默认聚类阈值为 0.8（比去重的 0.9 更宽松，用于跨源关联）。

### 跨源关联引擎 (`trend/correlator.py`)

```python
class CrossSourceCorrelator:
    """跨源关联器：检测同一话题在不同平台的出现."""

    def correlate(self, days=1, url_threshold=1.0, title_threshold=0.8):
        """对指定时间范围内的文章执行跨源关联:
        1. URL 精确匹配 (标准化后)
        2. 标题语义聚类
        3. 合并结果，计算 source_count
        """
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
  correlator.py 关联成功! 3个平台命中 → trend_score 大幅提升 → 标记 is_trending
```

### 内容指纹去重 (`trend/dedup.py`)

```python
def dedup_articles(session, days=7, threshold=0.9):
    """扫描未去重文章，通过标题相似度检测重复.
    相似度 > 0.9 → 标记 status = "duplicate"
    保留最早入库的文章，后续的标记为重复。
    """

def get_dedup_stats(session) -> dict[str, int]:
    """返回去重统计信息"""
```

## Layer 3: 实体发现与自动发现

### 实体发现引擎 (`trend/entity_discovery.py`)

```python
ENTITY_TYPES = {"person", "company", "project", "technology"}

def discover_entities(session, article_ids=None):
    """从已处理文章的 entities JSON 字段提取实体列表.
    - 解析每篇文章的 entities 字段
    - 通过 get_or_create 在 entities 表中创建或更新实体
    - 建立 article_entities 关联
    - 检测新实体 (is_new 标记)
    """
```

### 自动发现机制 (`trend/auto_discover.py`)

```python
def discover_emerging_researchers(session, days=30):
    """发现新兴研究员：统计 person 实体出现频次，
    首次出现在近期窗口内的标记为 emerging_researcher。"""

def discover_new_projects(session, days=7):
    """发现新 AI 项目：追踪 project 类型实体的首次出现和关联文章数。"""

def discover_new_companies(session, days=30):
    """发现新公司/组织：追踪 company 类型实体，首次出现时标记。"""
```

## 综合热点评分算法 (`trend/scorer.py`)

```python
# 权重
WEIGHT_PLATFORM = 0.35        # 单源热度
WEIGHT_CROSS_PLATFORM = 0.35  # 跨源关联
WEIGHT_VELOCITY = 0.20        # 增长速度

# 新实体加成
NOVELTY_BONUS_WITH_NEW_ENTITY = 1.2
NOVELTY_BONUS_DEFAULT = 1.0

# 热点阈值
TRENDING_THRESHOLD = 6.0

def calculate_trend_score(platform_hotness, cross_platform_bonus,
                          velocity, has_new_entity=False):
    """综合评分公式:
    score = (platform_hotness * 0.35 + cross_platform_bonus * 0.35
             + velocity * 0.20) * novelty_bonus * 10
    """
```

**评分含义:**

| 分数 | 含义 | 推送策略 |
|------|------|---------|
| 0-4 (low) | 低关注度 | 仅存入 Obsidian |
| 4-6 (normal) | 普通 | 存入 + 日报汇总 |
| 6-8 (notable) | 值得关注 | 存入 + 日报 + 标记热点 |
| 8-10 (major) | 重大热点 | 存入 + 即时推送 actionCard + 日报 |

## 自动发现机制

### 发现新兴研究员

```
模块: trend/auto_discover.py
方法:
  1. 统计近期 person 类型实体的出现频次
  2. 首次出现在近期窗口内 → 标记 "emerging_researcher"
  3. 关联其出现过的文章
```

### 发现新 AI 项目

```
模块: trend/auto_discover.py
方法:
  1. 追踪 project 类型实体的首次出现
  2. 统计关联文章数量
  3. 多源出现 → 确认为热门新项目
```

### 发现新公司/组织

```
模块: trend/auto_discover.py
方法:
  1. 从文章中提取 company 实体
  2. 与已知公司库对比
  3. 首次出现的公司 → 标记 "new_company"
  4. 后续追踪其出现频率和关联文章
```

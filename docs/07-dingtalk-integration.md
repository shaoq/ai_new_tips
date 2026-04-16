# 钉钉推送方案

## 前置配置

### 创建钉钉自定义机器人

1. 打开钉钉客户端，选择目标群聊
2. 群设置 → 机器人 → 添加机器人 → 选择"自定义机器人 (Webhook)"
3. 输入机器人名称
4. 配置安全设置（推荐：签名模式）
5. 复制 Webhook URL 和 Secret

### 配置项

```yaml
# ~/.ainews/config.yaml
dingtalk:
  webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  secret: "SEC-xxx"                      # HMAC-SHA256 签名密钥
  keyword: "AI News"                     # 关键词安全模式 (可选)
```

### 签名计算

```python
import time, hmac, hashlib, base64, urllib.parse

def sign_dingtalk(secret: str) -> tuple[str, str]:
    """计算钉钉 Webhook 签名"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign

# 最终请求 URL:
# https://oapi.dingtalk.com/robot/send?access_token=xxx&timestamp={ts}&sign={sign}
```

## 速率限制

| 限制 | 值 |
|------|-----|
| 每分钟每机器人 | 20 条消息 |
| 超限惩罚 | 封禁 10 分钟 |
| Markdown 文本长度 | 建议 ≤ 1000 字符 |
| ActionCard 文本长度 | 建议 ≤ 500 字符 |

## 推送策略

```
┌────────────────────────────────────────────────────────┐
│              钉钉推送策略                                │
├──────────┬──────────┬──────────────┬───────────────────┤
│ 时间      │ 格式     │ 触发条件      │ 内容              │
├──────────┼──────────┼──────────────┼───────────────────┤
│ 08:00    │ feedCard │ 定时          │ 晨报: Top 5-10篇  │
│ 12:30    │ actionCard│ trend≥8     │ 仅推送热点         │
│ 20:00    │ feedCard │ 定时          │ 晚报: 全部增量     │
│ 周日20:30│ markdown │ 定时          │ 周报: 统计+Top5   │
└──────────┴──────────┴──────────────┴───────────────────┘

推送控制:
├─ 同一篇文章不重复推送 (dingtalk_sent 字段)
├─ 即时推送每天最多 3 条 (防打扰)
└─ 无新热点时不推送 (中午那次可能跳过)
```

## 消息格式

### 1. feedCard (晨报/晚报)

适用：展示 5-10 篇精选文章，含标题、缩略图、链接。

```json
{
    "msgtype": "feedCard",
    "feedCard": {
        "links": [
            {
                "title": "🔥 GPT-6 正式发布：实时推理能力重大突破 (趋势分 8.7)",
                "messageURL": "https://openai.com/blog/gpt-6",
                "picURL": "https://openai.com/favicon.ico"
            },
            {
                "title": "🔥 DeepSeek R2 开源发布，性能比肩 GPT-6 (趋势分 8.2)",
                "messageURL": "https://github.com/deepseek-ai/DeepSeek-R2",
                "picURL": "https://github.com/favicon.ico"
            },
            {
                "title": "新推理架构论文：Sparse Attention V2 (HF 128票)",
                "messageURL": "https://arxiv.org/abs/2404.xxxxx",
                "picURL": "https://arxiv.org/favicon.ico"
            },
            {
                "title": "Meta 发布 Llama 4：开源模型新标杆 (HN 642分)",
                "messageURL": "https://ai.meta.com/blog/llama-4",
                "picURL": "https://ai.meta.com/favicon.ico"
            },
            {
                "title": "Claude 5 系统提示词泄露分析 (Reddit 1.2k赞)",
                "messageURL": "https://reddit.com/r/ChatGPT/comments/xxx",
                "picURL": "https://reddit.com/favicon.ico"
            }
        ]
    }
}
```

**渲染效果:**

```
┌─────────────────────────────────────────────────────┐
│  🤖 AI News Tips                                     │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 🖼️  [OpenAI]                                    │ │
│  │ 🔥 GPT-6 正式发布：实时推理能力重大突破 (趋势分 8.7)│ │
│  │ → 点击阅读原文                                   │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 🖼️  [DeepSeek]                                  │ │
│  │ 🔥 DeepSeek R2 开源发布... (趋势分 8.2)         │ │
│  │ → 点击阅读原文                                   │ │
│  └─────────────────────────────────────────────────┘ │
│  ...                                                  │
│  📊 本批共 23 篇新文章 | 已同步至 Obsidian           │
└─────────────────────────────────────────────────────┘
```

### 2. actionCard (即时热点)

适用：单篇重大热点，trend_score ≥ 8.5 或跨 3+ 平台命中。

```json
{
    "msgtype": "actionCard",
    "actionCard": {
        "title": "🚨 AI 突发：GPT-6 发布",
        "text": "### ⚡ OpenAI 发布 GPT-6\n\n实时推理能力重大突破\n\n**🔥 趋势分: 8.7/10**\n**📊 跨 3 平台命中**: HN 842分 | Reddit 1.2k赞 | 5个RSS源\n\nOpenAI于今日正式发布GPT-6模型，最显著的突破是实现了实时多步推理能力。在数学、编程基准上大幅超越前代。\n\n*2026-04-13 08:32 | AI News Tips*",
        "btnOrientation": "1",
        "btns": [
            {
                "title": "📖 阅读原文",
                "actionURL": "https://openai.com/blog/gpt-6"
            },
            {
                "title": "📝 查看 Obsidian",
                "actionURL": "obsidian://open?vault=MyVault&file=AI-News/Industry/2026-04-13-openai-gpt6"
            }
        ]
    }
}
```

### 3. markdown (周报)

适用：每周日推送本周统计摘要。

```json
{
    "msgtype": "markdown",
    "markdown": {
        "title": "AI News 周报 2026-W15",
        "text": "## AI News Tips - 周报 (W15)\n\n---\n\n### 📊 本周数据\n\n- **总文章**: 156 篇 (↑12% vs 上周)\n- **热点文章**: 23 篇\n- **新发现人物**: 7 人\n- **新发现项目**: 4 个\n\n### 🔥 本周 Top 5 热点\n\n**1. GPT-6 发布** (趋势分 9.1)\n> 5平台命中 · 12篇文章讨论\n\n**2. DeepSeek R2 开源** (趋势分 8.8)\n> 4平台命中 · 开源社区热议\n\n**3. EU AI Act 执法开始** (趋势分 8.5)\n> 政策类 · 影响全球AI公司\n\n**4. Llama 4 发布** (趋势分 8.2)\n> HN 最高分 1200+\n\n**5. Sparse Attention V2 论文** (趋势分 7.9)\n> HF 256票 · 引用快速增长\n\n### 📈 分类分布\n\n- industry: 58 | research: 42 | tools: 31\n- safety: 15 | policy: 10\n\n---\n*完整数据已同步至 Obsidian 仪表盘*"
    }
}
```

### 4. markdown (午间速报)

适用：中午仅推送上午新热点。

```json
{
    "msgtype": "markdown",
    "markdown": {
        "title": "AI News 午间速报",
        "text": "## 📰 午间速报 (3篇热点)\n\n**1. Anthropic 发布 Claude 5 技术报告**\n> 🔥 趋势分 8.3 | [阅读原文](https://anthropic.com/news/claude-5)\n\n**2. Google 发布 Gemini 2.5 Flash**\n> 🔥 趋势分 7.8 | [阅读原文](https://deepmind.google/gemini)\n\n**3. 开源项目 Qwen3 发布**\n> 📊 HF 89票 | [阅读原文](https://huggingface.co/Qwen/Qwen3)\n\n---\n本批共 8 篇 | 今日累计: 31 篇 | 已同步至 Obsidian"
    }
}
```

## 推送控制逻辑

```python
class DingTalkPublisher:
    def should_push(self, article: Article, push_type: str) -> bool:
        """判断是否应该推送某篇文章"""
        if article.dingtalk_sent:
            return False  # 已推送过

        if push_type == "trending_only":
            return article.trend_score >= 8.0
        elif push_type == "daily":
            return True  # 日报包含所有新文章
        elif push_type == "instant":
            return article.trend_score >= 8.5  # 即时推送仅限高分
        return False

    def should_skip_noon(self) -> bool:
        """中午是否跳过推送"""
        return self.trending_count == 0  # 无热点则不打扰

    def check_daily_instant_limit(self) -> bool:
        """检查即时推送每日上限"""
        return self.today_instant_count < 3  # 每天最多3条即时推送
```

## 推送策略实现

`publisher/strategy.py` 是推送策略引擎，负责去重判断、每日上限控制和文章查询。核心类为 `PushStrategy`。

### 时间窗口选择

推送模式根据当前小时自动选择：

| 时间段 | 模式 | 查询方法 | 说明 |
|--------|------|----------|------|
| 06:00-11:00 | `morning_digest` | `query_morning_articles(limit=10)` | 按趋势分降序取 Top 10 |
| 11:00-15:00 | `noon_update` | `query_noon_articles()` | 仅 trend_score >= 8 的热点 |
| 其他 | `evening_digest` | `query_evening_articles()` | 今日全量增量 |

### 午间跳过逻辑

`should_skip_noon()` 判断午间是否跳过推送：
- 查询今日新文章中 trend_score >= 8.0 的热点文章
- 如果查询结果为空（无新热点），返回 `True` 跳过推送
- 有热点时按 trend_score 降序推送

### 晨报文章排序

`query_morning_articles(limit)` 查询逻辑：
- 筛选条件：`dingtalk_sent == False` 且 `processed == True`
- 按 `trend_score` 降序排列
- 默认取 Top 10 篇

### 每日 actionCard 上限

- 常量 `DAILY_ACTIONCARD_LIMIT = 3`，每天最多推送 3 条 actionCard
- `should_push()` 在 `push_type == "actioncard"` 时检查 `_daily_actioncard_count()`
- 超过上限则跳过，通过 `push_log` 表统计当日 actionCard 推送数量

### 去重机制

- feedCard 去重：通过 `article.dingtalk_sent` 字段判断，已推送则跳过
- actionCard 去重：查询 `push_log` 表中是否已有 `push_type == "actioncard"` 的记录

## 消息格式化

`publisher/formatter.py` 负责将文章数据构建为钉钉消息体，所有函数接收 `dict` 类型参数（非 Article 对象）。

### 格式构建函数

| 函数 | 消息类型 | 用途 |
|------|----------|------|
| `build_feedcard(articles, title)` | feedCard | 晨报/晚报，展示多篇文章含标题、链接、缩略图 |
| `build_actioncard(article)` | actionCard | 即时热点，单篇文章含摘要和操作按钮 |
| `build_markdown_weekly(stats, top_articles)` | markdown | 周报，包含统计数据和 Top 5 热点 |
| `build_markdown_noon(articles)` | markdown | 午间速报，列出热点文章 |
| `build_test_message()` | markdown | 测试消息，验证 Webhook 连通性 |

### 字段映射

消息构建器从传入的 `dict` 中读取以下字段：

- `title` — 原始标题（回退值）
- `title_zh` — 中文标题（优先使用）
- `url` — 原文链接
- `summary_zh` — 中文摘要（actionCard 使用，限 480 字符）
- `trend_score` — 趋势分（markdown 格式显示）
- `source_name` — 来源名称（午间速报显示）
- `pic_url` — 缩略图 URL（feedCard 使用，可选）
- `obsidian_url` — Obsidian 链接（actionCard 按钮使用，可选）

### 文本长度限制

- feedCard 标题：无硬限制
- actionCard 正文：480 字符截断（钉钉建议 <= 500 字符）
- markdown 正文：2000 字符截断

## Article 对象转换

`publisher/formatter.py` 的所有构建函数接收 `dict` 类型参数，而非 SQLModel `Article` 对象。调用方必须先将 `Article` 对象转换为字典。

### 转换函数

在 `cli/push.py` 中，`_article_to_dict()` 负责转换：

```python
def _article_to_dict(article: Article) -> dict[str, str | float]:
    """将 Article 对象转换为消息构建器所需的字典."""
    return {
        "title": article.title,
        "url": article.url,
        "summary_zh": article.summary_zh,
        "trend_score": article.trend_score,
        "source_name": article.source_name,
        "category": article.category,
        "obsidian_url": "",  # Obsidian URL 需要从其他模块获取
    }
```

### 为什么需要转换

`fix-push-type-mismatch` 修复引入了此转换层，原因：

1. **解耦**: formatter 不依赖 SQLModel 定义，保持纯数据处理职责
2. **字段选择**: 仅提取消息构建所需字段，避免传递不必要的数据
3. **类型安全**: dict 的值类型明确为 `str | float`，与 formatter 的 `Any` 参数兼容

在 pipeline 的 `_step_push()` 中也使用了类似的转换逻辑，直接构造 dict 列表传入 `build_feedcard()`。

## Pipeline 集成

完整流水线通过 `ainews run` 命令执行，共 6 个步骤，钉钉推送为最后一步。

### 流水线步骤

```
Fetch → Process → Dedup → Trend → Sync Obsidian → Push DingTalk
  1        2        3       4          5                 6
```

### Step 6: Push DingTalk

在 `cli/run.py` 的 `_step_push()` 函数中实现：

1. 初始化 `PushStrategy` 和 `DingTalkClient`
2. 根据选项查询文章：
   - `--trending-only-push`：调用 `strategy.query_trending_articles()` 获取热点
   - 默认：调用 `strategy.query_morning_articles()` 获取 Top 10
3. 将 Article 对象转换为 dict 列表
4. 调用 `build_feedcard()` 构建消息
5. 调用 `client.send()` 发送到钉钉
6. 返回推送文章数量

### 跳过选项

- `--no-push` / `--skip-push`：跳过 Push 步骤（`skip_push=True`）
- `--trending-only-push`：仅推送 trend_score >= 8 的热点文章

### 与 `ainews push dingtalk` 的区别

`ainews run` 的推送是简化版，仅支持 feedCard 格式。完整的推送功能（actionCard、午间速报、周报、自动时段选择）需通过 `ainews push dingtalk` 命令使用，参见 `cli/push.py`。

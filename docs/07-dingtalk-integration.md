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

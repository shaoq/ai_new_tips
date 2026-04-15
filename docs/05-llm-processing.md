# LLM 智能处理

## 配置设计

用户自行配置 LLM，程序根据配置调用。默认使用 Anthropic 协议。

```yaml
# ~/.ainews/config.yaml
llm:
  base_url: "https://api.anthropic.com"    # 用户自配
  api_key: "sk-ant-xxx"                     # 用户自配
  model: "claude-haiku-4-5-20251001"        # 用户自配
  max_tokens: 4096
```

### 客户端抽象

```python
# 基于 httpx 直接调用 Anthropic Messages API 协议
# 兼容所有支持 Anthropic 协议的服务商（仅需 base_url + api_key）

import httpx

client = httpx.Client(
    base_url=config.llm.base_url,
    headers={
        "x-api-key": config.llm.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    },
    timeout=120.0,
)

response = client.post("/v1/messages", json={
    "model": config.llm.model,
    "max_tokens": config.llm.max_tokens,
    "messages": [{"role": "user", "content": prompt}],
})

# 响应格式: {"content": [{"type": "text", "text": "..."}], ...}
text = "\n".join(block["text"] for block in response.json()["content"] if block["type"] == "text")
```

## 处理能力

每篇新文章经过以下 LLM 处理步骤：

### 1. 自动分类

**输入:** 文章标题 + 内容摘要

**输出:**

```json
{
    "category": "industry",
    "confidence": 0.92
}
```

**可选分类:**

| 分类 | 说明 |
|------|------|
| `industry` | 行业动态、产品发布、融资、公司新闻 |
| `research` | 学术论文、研究突破、新方法 |
| `tools` | AI 工具、应用、开源项目 |
| `safety` | AI 安全、对齐、伦理 |
| `policy` | 政策法规、监管 |

**Prompt:**

```
对以下AI相关文章进行分类。

可选分类: industry, research, tools, safety, policy

标题: {title}
内容: {content[:2000]}

返回JSON: {"category": "分类", "confidence": 0.0-1.0}
只返回JSON，不要其他文本。
```

### 2. 中文摘要

**输入:** 英文原文内容

**输出:** 2-3 句中文摘要

**Prompt:**

```
用2-3句中文总结以下AI文章的核心要点。
只返回摘要文本，不要其他内容。

标题: {title}
内容: {content[:3000]}
```

**示例:**

```
输入: "OpenAI Announces GPT-6 with Real-Time Reasoning Capabilities..."
输出: "OpenAI发布GPT-6模型，最显著的突破是实现了实时多步推理能力。
      在GSM8K、HumanEval和MATH基准测试中分别达到97.2%、96.8%和94.5%的准确率。"
```

### 3. 相关性评分

**输入:** 文章内容 + 用户兴趣配置

**输出:** 1-10 分数

**Prompt:**

```
评估以下AI文章对AI技术从业者的相关性，打分1-10。
考虑因素: 技术深度、行业影响、创新性、实用性。

标题: {title}
内容: {content[:2000]}

返回JSON: {"relevance": 1-10, "reason": "评分理由(一句话)"}
```

### 4. 实体提取

**输入:** 文章内容

**输出:** 结构化实体列表

**Prompt:**

```
从以下文章中提取所有命名实体。

文章内容:
{content[:3000]}

返回JSON:
{
    "people": ["人名列表"],
    "companies": ["公司/组织名列表"],
    "projects": ["项目/产品/模型名列表"],
    "technologies": ["具体技术名称列表"]
}
只返回有效JSON。
```

### 5. 标签提取

**输入:** 文章内容 + 已有分类

**输出:** 标签列表

**Prompt:**

```
为以下AI文章生成3-5个标签。

标题: {title}
分类: {category}
内容: {content[:2000]}

返回JSON: {"tags": ["tag1", "tag2", ...]}
标签使用英文小写，用连字符连接多词。
```

## 批量处理优化

```
处理流程优化:

  Option 1: 单次调用合并 (节省 token)
  ┌────────────────────────────────────────┐
  │ 一次 LLM 调用同时完成:                  │
  │ 分类 + 摘要 + 评分 + 实体 + 标签        │
  │                                        │
  │ Prompt: 返回一个完整 JSON               │
  │ {                                      │
  │   "category": "industry",              │
  │   "summary_zh": "...",                 │
  │   "relevance": 9,                      │
  │   "entities": {...},                   │
  │   "tags": [...]                        │
  │ }                                      │
  └────────────────────────────────────────┘

  Option 2: 拆分调用 (更灵活但更贵)
  每个处理步骤单独调用，可独立重试

  推荐: Option 1，一次调用完成所有处理
```

### 合并处理 Prompt

```
分析以下AI相关文章，返回完整分析结果。

标题: {title}
来源: {source_name}
内容: {content[:3000]}

返回JSON（不要其他文本）:
{
    "category": "industry|research|tools|safety|policy",
    "category_confidence": 0.0-1.0,
    "summary_zh": "2-3句中文核心摘要",
    "relevance": 1-10,
    "relevance_reason": "评分理由",
    "tags": ["tag1", "tag2", "tag3"],
    "entities": {
        "people": [],
        "companies": [],
        "projects": [],
        "technologies": []
    }
}
```

### JSON 解析健壮性

`parse_json_response` 函数对 LLM 返回的原始文本做了两层防御处理，确保 JSON 解析的稳定性：

1. **控制字符清除**：在调用 `json.loads()` 之前，使用正则 `[\x00-\x1f]` 移除所有 ASCII 控制字符。这主要应对 LLM 在 JSON 字符串值中输出未转义的换行符 (`\n`)、制表符 (`\t`) 或其他控制字符的情况——尤其是 `summary_zh`（中文摘要）字段中出现此类问题的概率较高。

2. **Markdown 代码块提取**：当 LLM 将 JSON 包裹在 Markdown 代码块（` ```json ... ``` `）中时，函数会自动提取其中的 JSON 内容再进行解析，兼容 LLM 偶尔不严格遵守"只返回 JSON"指令的情况。

## 成本估算

| 模型 | 每篇约消耗 | 50篇/天 | 月费用 |
|------|-----------|---------|-------|
| Claude Haiku | ~500 token | ~25K token | ~$1.5/月 |
| Claude Sonnet | ~500 token | ~25K token | ~$7.5/月 |
| 本地模型 (Ollama) | 免费 | 免费 | $0 |

用户可根据 `config.yaml` 中的配置自由选择模型和供应商。

## 处理进度输出

批量处理文章时（`ainews run` 或 `ainews process`），终端会每处理完 5 篇文章打印一行进度：

```
  ▸ Process...
    · Processed 5/50 articles
    · Processed 10/50 articles
    · Processed 15/50 articles
    ...
    · Processed 50/50 articles
       OK     Process (75.3s, 50 items)
```

- 进度基于 `rich.console.Console`，在 `processor/processor.py` 的 `process_unprocessed()` 和 `process_all_force()` 中实现
- 少于 5 篇时仅在全部完成时打印一行（如 `Processed 3/3 articles`）
- 0 篇时不打印进度行

# LLM 智能处理

## 配置设计

用户自行配置 LLM，程序根据配置调用。默认使用 Anthropic 协议。

```yaml
# ~/.ainews/config.yaml
llm:
  base_url: "https://api.anthropic.com"    # 用户自配
  api_key: "sk-ant-xxx"                     # 用户自配
  model: "claude-haiku-4-5-20251001"        # 用户自配
  max_tokens: 1024
```

### 客户端抽象

```python
# 统一使用 Anthropic 协议 (Messages API)
# 兼容所有支持 Anthropic 协议的服务商

from anthropic import Anthropic

client = Anthropic(
    base_url=config.llm.base_url,
    api_key=config.llm.api_key,
)

response = client.messages.create(
    model=config.llm.model,
    max_tokens=config.llm.max_tokens,
    messages=[{"role": "user", "content": prompt}]
)
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

## 成本估算

| 模型 | 每篇约消耗 | 50篇/天 | 月费用 |
|------|-----------|---------|-------|
| Claude Haiku | ~500 token | ~25K token | ~$1.5/月 |
| Claude Sonnet | ~500 token | ~25K token | ~$7.5/月 |
| 本地模型 (Ollama) | 免费 | 免费 | $0 |

用户可根据 `config.yaml` 中的配置自由选择模型和供应商。

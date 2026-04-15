"""LLM Prompt 模板集中管理."""

MERGED_PROCESS_PROMPT = """\
你是一名 AI 新闻分析师。请分析以下文章并返回 JSON 格式的分析结果。

## 文章信息

**标题**: {title}
**来源**: {source_name}
**内容**: {content}

## 分析要求

请返回一个 JSON 对象，包含以下字段：

- `title_zh`: 文章标题的简洁中文翻译。如果原标题已是中文则直接返回原标题
- `category`: 分类，必须为以下枚举值之一:
  - `industry` - 行业动态（产品发布、商业合作、市场趋势）
  - `research` - 学术研究（论文、新方法、技术突破）
  - `tools` - 工具和资源（开源项目、API、开发工具）
  - `safety` - AI 安全与伦理（安全研究、政策讨论、风险分析）
  - `policy` - 政策法规（监管、法律、合规）
- `category_confidence`: 分类置信度，0.0 到 1.0 之间的浮点数
- `summary_zh`: 中文摘要，2-3 句话，简洁准确地概括文章核心内容
- `relevance`: AI 领域相关性评分，1 到 10 的整数（1=几乎无关，10=高度相关）
- `relevance_reason`: 相关性评分的简要理由，一句话
- `tags`: 3-5 个英文小写标签，多词用连字符连接（如 "large-language-model"）
- `entities`: 提取的命名实体对象，包含以下四类列表:
  - `people`: 提及的人物姓名
  - `companies`: 提及的公司/组织名称
  - `projects`: 提及的项目/产品名称
  - `technologies`: 提及的技术名称

## 输出格式

只返回 JSON，不要包含其他文本。不要用 markdown code block 包裹。\
"""

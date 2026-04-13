## ADDED Requirements

### Requirement: 每日笔记追加
系统 SHALL 将本次同步的文章摘要追加到当日 daily note。每次运行生成一个 `## HH:MM 更新 (N篇)` 段落，包含所有本次同步文章的摘要列表。

#### Scenario: 追加更新段落
- **WHEN** 本次同步了 10 篇文章，当前时间为 08:30
- **THEN** 在当日 daily note 追加 `## 08:30 更新 (10篇)` 段落，每篇文章一行：`- [[{date-slug}|{短标题}]] {trend_score_emoji} {relevance} {category}`

#### Scenario: 同一日多次运行
- **WHEN** 当日 08:00 已追加过段落，12:30 再次同步 8 篇文章
- **THEN** 在已有内容后追加新的 `## 12:30 更新 (8篇)` 段落，不影响 08:00 段落

### Requirement: 每日笔记格式
每个更新段落中的文章摘要行 SHALL 使用以下格式：
- 热点文章（is_trending=true）前缀 `🔥`
- 链接使用 `[[date-slug|短标题]]` 内部链接格式
- 每行末尾显示 relevance 评分和 category

#### Scenario: 热点文章摘要行
- **WHEN** 一篇 is_trending=true、relevance=9.0、category=industry 的文章
- **THEN** 摘要行为 `- [[2026-04-13-openai-gpt6|GPT-6 发布]] 🔥 9.0 industry`

#### Scenario: 普通文章摘要行
- **WHEN** 一篇 is_trending=false、relevance=7.0、category=research 的文章
- **THEN** 摘要行为 `- [[2026-04-13-sparse-attn|Sparse Attention V2]] 7.0 research`

### Requirement: 每日笔记头部
当日 daily note 不存在时，系统 SHALL 创建文件并写入头部：`# AI News - {YYYY-MM-DD}` 标题和 Dataview 概览表（显示当日所有文章的 relevance、source_name、category，按 trend_score 排序）。

#### Scenario: 首次创建每日笔记
- **WHEN** 2026-04-13 的 daily note 不存在
- **THEN** 创建 `AI-News/Daily/2026-04-13.md`，写入标题和 Dataview 概览表

#### Scenario: 每日笔记已存在
- **WHEN** 2026-04-13 的 daily note 已存在且有内容
- **THEN** 仅追加新的更新段落，不修改已有头部和段落

### Requirement: REST API 模式每日笔记
REST API 可用时，系统 SHALL 使用 `PATCH /periodic/daily/` + Headers `Target-Type: heading`、`Operation: append` 追加内容。

#### Scenario: REST API 追加成功
- **WHEN** 调用 `PATCH /periodic/daily/` 追加 `## 08:30 更新 (10篇)` 段落
- **THEN** 请求 Headers 包含 `Content-Type: text/markdown`、`Target-Type: heading`、`Operation: append`，请求体为段落内容

### Requirement: 文件系统降级模式每日笔记
REST API 不可用时，系统 SHALL 直接操作文件 `{vault_path}/AI-News/Daily/{YYYY-MM-DD}.md`。文件不存在时创建并写入头部；文件存在时追加内容。

#### Scenario: 文件系统模式创建每日笔记
- **WHEN** 处于文件系统降级模式且当日 daily note 不存在
- **THEN** 创建 `{vault_path}/AI-News/Daily/2026-04-13.md`，写入头部 + 本次更新段落

#### Scenario: 文件系统模式追加每日笔记
- **WHEN** 处于文件系统降级模式且当日 daily note 已存在
- **THEN** 在文件末尾追加换行和新的更新段落

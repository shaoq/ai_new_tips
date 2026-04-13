## ADDED Requirements

### Requirement: 文章同步查询
系统 SHALL 查询 SQLite 数据库中 `obsidian_synced = false` 且 `processed = true` 且 `status != 'duplicate'` 的文章，按 `trend_score DESC` 排序后执行同步。

#### Scenario: 同步未写入文章
- **WHEN** 执行 `ainews sync obsidian` 且数据库中有 15 篇未同步文章
- **THEN** 系统按 trend_score 降序处理这 15 篇文章，逐篇写入 Obsidian

#### Scenario: 无新文章
- **WHEN** 执行 `ainews sync obsidian` 且所有文章已同步
- **THEN** 系统输出 "No new articles to sync" 并退出

### Requirement: 文章文件路径生成
系统 SHALL 按以下规则生成文章文件路径：`AI-News/{category}/{YYYY-MM-DD}-{slug}.md`。其中 slug 由标题生成：小写化、移除非字母数字字符、空格转连字符、截断 60 字符。

#### Scenario: 标准标题 slug 生成
- **WHEN** 文章标题为 "GPT-6 Announced: Real-Time Reasoning Breakthrough"
- **THEN** slug 为 `gpt-6-announced-real-time-reasoning-breakthrough`，完整路径为 `AI-News/industry/2026-04-13-gpt-6-announced-real-time-reasoning-breakthrough.md`

#### Scenario: 中文标题 slug 生成
- **WHEN** 文章标题为 "深度学习新架构：Transformer 的进化"
- **THEN** 系统移除中文字符，slug 基于剩余英文/数字生成，若结果为空则使用 URL hash 作为 slug

### Requirement: YAML frontmatter 生成
系统 SHALL 为每篇文章生成 YAML frontmatter，包含以下字段：title、date、source、source_name、author、tags（YAML 列表）、category、status、relevance、trend_score、is_trending、summary、platforms（YAML 列表）、entities（嵌套结构：people/companies/projects/tech）、imported_at、dingtalk_sent。

#### Scenario: 完整 frontmatter
- **WHEN** 渲染一篇包含所有字段的文章
- **THEN** 生成的 frontmatter 包含所有 16 个字段，tags 为 YAML 列表格式，entities 为嵌套字典

#### Scenario: 可选字段缺失
- **WHEN** 文章的 author 字段为空
- **THEN** frontmatter 中省略 author 字段，不输出空值

### Requirement: Markdown 正文生成
系统 SHALL 为每篇文章生成 Markdown 正文，包含三个部分：中文摘要（`## 中文摘要`）、原文链接（`## 原文链接`）、关联实体（`## 关联`，使用 `[[双链]]` 格式）。

#### Scenario: 包含实体的文章正文
- **WHEN** 文章关联了 3 个实体（Sam Altman、OpenAI、GPT-6）
- **THEN** 正文 `## 关联` 部分包含 `[[Sam-Altman]]`、`[[OpenAI]]`、`[[GPT-6]]` 双向链接

#### Scenario: 无实体的文章正文
- **WHEN** 文章未提取到任何实体
- **THEN** 正文省略 `## 关联` 部分

### Requirement: REST API 模式文章写入
REST API 可用时，系统 SHALL 使用 `PUT /vault/AI-News/{category}/{date-slug}.md` 创建文章文件。

#### Scenario: 创建新文章
- **WHEN** 同步一篇新文章且 REST API 可用
- **THEN** 调用 `PUT /vault/AI-News/Industry/2026-04-13-openai-gpt6.md`，请求体为完整 Markdown 内容

#### Scenario: 文章已存在（REST API）
- **WHEN** 文章文件在 Vault 中已存在
- **THEN** 使用 `PUT` 覆盖更新（frontmatter + 正文完整替换）

### Requirement: 文件系统降级模式文章写入
REST API 不可用时，系统 SHALL 直接写入文件到 `{vault_path}/AI-News/{category}/{date-slug}.md`。

#### Scenario: 创建目录和文件
- **WHEN** 处于文件系统模式且 `AI-News/Industry/` 目录不存在
- **THEN** 系统创建目录后写入文件

#### Scenario: 文件已存在（文件系统）
- **WHEN** 文章文件在文件系统中已存在
- **THEN** 跳过该文件，日志记录已存在，避免覆盖已有内容（因为无法精确更新 frontmatter）

### Requirement: 同步成功标记
每篇文章成功写入后，系统 SHALL 更新数据库：设置 `obsidian_synced = true`，记录 `obsidian_path` 为写入路径。

#### Scenario: 标记同步成功
- **WHEN** 文章 `2026-04-13-openai-gpt6` 成功写入 Obsidian
- **THEN** 数据库中该文章的 `obsidian_synced` 更新为 `true`，`obsidian_path` 更新为 `AI-News/Industry/2026-04-13-openai-gpt6.md`

### Requirement: 已同步文章的 frontmatter 更新
当已同步文章的动态字段（trend_score、platforms、is_trending）变更时，系统 SHALL 通过 REST API `PATCH` 更新 frontmatter。文件系统模式下跳过更新。

#### Scenario: trend_score 更新
- **WHEN** 文章已同步但 trend_score 从 7.0 变为 8.7（跨源命中）
- **THEN** 系统通过 `PATCH /vault/{path}` + `Target-Type: frontmatter` 更新 trend_score、platforms、is_trending 字段

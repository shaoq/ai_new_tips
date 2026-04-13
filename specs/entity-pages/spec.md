## ADDED Requirements

### Requirement: 实体页面同步
系统 SHALL 从数据库 `entities` 表和 `article_entities` 关联表查询所有实体及其关联文章，为每个实体创建或更新 Obsidian 页面。页面路径为 `AI-News/Entities/{type_plural}/{name}.md`，其中 type_plural 为 People/Companies/Projects。

#### Scenario: 同步所有实体
- **WHEN** 执行 `ainews sync obsidian --sync-entities`
- **THEN** 系统查询所有实体，按 type 分组，为每个实体创建/更新页面

### Requirement: 实体文件名规范化
实体名称 SHALL 转换为有效文件名：空格转连字符，移除特殊字符（保留字母、数字、连字符），首字母大写。

#### Scenario: 人物名称规范化
- **WHEN** 实体名称为 "Sam Altman"
- **THEN** 文件名为 `Sam-Altman.md`，路径为 `AI-News/Entities/People/Sam-Altman.md`

#### Scenario: 项目名称规范化
- **WHEN** 实体名称为 "GPT-6"
- **THEN** 文件名为 `GPT-6.md`，路径为 `AI-News/Entities/Projects/GPT-6.md`

#### Scenario: 包含特殊字符的名称
- **WHEN** 实体名称为 "AlphaGo (DeepMind)"
- **THEN** 文件名为 `AlphaGo-DeepMind.md`

### Requirement: 实体页面格式
每个实体页面 SHALL 包含 YAML frontmatter（type、company、first_seen、mention_count、last_seen）和 Markdown 正文（标题 + 类型/公司/首次出现/提及次数信息 + Dataview 相关文章列表查询）。

#### Scenario: 人物实体页面
- **WHEN** 为 "Sam Altman" 创建实体页面
- **THEN** 页面包含 frontmatter（type: person、company: `[[OpenAI]]`、first_seen: 2026-04-01、mention_count: 28）和正文（标题 `# Sam Altman` + 属性列表 + Dataview 查询 `LIST FROM "AI-News" WHERE contains(entities.people, this.file.name) SORT date DESC LIMIT 10`）

#### Scenario: 公司实体页面
- **WHEN** 为 "OpenAI" 创建实体页面
- **THEN** 页面 frontmatter 包含 type: company，正文 Dataview 查询 `WHERE contains(entities.companies, this.file.name)`

#### Scenario: 项目实体页面
- **WHEN** 为 "GPT-6" 创建实体页面
- **THEN** 页面 frontmatter 包含 type: project，正文 Dataview 查询 `WHERE contains(entities.projects, this.file.name)`

### Requirement: 实体页面创建（REST API）
REST API 可用时，系统 SHALL 先通过 `POST /search/simple/` 检查实体页面是否已存在。不存在则 `PUT` 创建，存在则 `PATCH` 更新 frontmatter。

#### Scenario: 创建新实体页面
- **WHEN** 实体 "Dario Amodei" 的页面不存在
- **THEN** 调用 `PUT /vault/AI-News/Entities/People/Dario-Amodei.md` 创建页面

#### Scenario: 更新已有实体页面
- **WHEN** 实体 "Sam Altman" 的页面已存在，mention_count 从 28 变为 35
- **THEN** 调用 `PATCH /vault/AI-News/Entities/People/Sam-Altman.md` + `Target-Type: frontmatter` 更新 mention_count 和 last_seen

### Requirement: 实体页面创建（文件系统降级）
REST API 不可用时，系统 SHALL 检查文件是否存在。不存在则创建，存在则读取并更新 frontmatter 部分。

#### Scenario: 文件系统创建实体页面
- **WHEN** 处于文件系统降级模式且实体页面不存在
- **THEN** 创建 `{vault_path}/AI-News/Entities/People/Sam-Altman.md`

#### Scenario: 文件系统更新实体页面
- **WHEN** 处于文件系统降级模式且实体页面已存在
- **THEN** 读取文件，解析 YAML frontmatter，更新 mention_count 和 last_seen，重新写入

### Requirement: 实体与文章的双向链接
文章 Markdown 正文中的 `## 关联` 部分 SHALL 使用 `[[name]]` 格式链接到实体页面。实体页面通过 Dataview 查询自动反向链接到所有提及该实体的文章。

#### Scenario: 文章中引用实体
- **WHEN** 文章涉及 "Sam Altman" 和 "OpenAI"
- **THEN** 文章正文 `## 关联` 部分包含 `[[Sam-Altman]]` 和 `[[OpenAI]]`

#### Scenario: 实体页面反向查询
- **WHEN** 用户在 Obsidian 中打开 "Sam-Altman" 页面
- **THEN** Dataview 查询自动列出所有 `entities.people` 包含 "Sam-Altman" 的文章

### Requirement: 实体类型路由
系统 SHALL 根据实体 type 字段路由到不同目录：person -> `Entities/People/`，company -> `Entities/Companies/`，project -> `Entities/Projects/`，technology -> 暂不创建页面（技术标签通过 tags 管理）。

#### Scenario: 人物路由
- **WHEN** 实体 type 为 "person"
- **THEN** 页面路径为 `AI-News/Entities/People/{name}.md`

#### Scenario: 技术标签跳过
- **WHEN** 实体 type 为 "technology"
- **THEN** 跳过页面创建，仅通过文章 tags 管理

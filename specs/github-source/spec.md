## ADDED Requirements

### Requirement: GitHub 配置模型
系统 SHALL 在配置中支持 GitHub 分组，包含以下字段：enabled (BOOL, 默认 true)、token (TEXT, 可选 PAT)、topics (LIST, 默认 ["machine-learning","llm","ai","transformer"])、languages (LIST, 默认 ["python","typescript"])、min_stars (INT, 默认 50)、fetch_interval_minutes (INT, 默认 360)。

#### Scenario: 配置加载
- **WHEN** 系统读取包含 `sources.github` 配置的 config.yaml
- **THEN** GitHub 配置正确解析，topics 和 languages 列表可自定义

#### Scenario: 无 PAT token
- **WHEN** GitHub token 为空
- **THEN** 系统使用未认证模式（60 req/h 限额），并在 doctor 检查中提示建议配置 PAT

#### Scenario: 有 PAT token
- **WHEN** GitHub token 已配置
- **THEN** httpx 请求头包含 `Authorization: token {pat}`，限额提升到 5000 req/h

### Requirement: GitHub Search API 调用
GitHub Fetcher SHALL 使用 httpx 调用 GitHub Search API `GET /search/repositories`，按 topics + languages 构建查询，时间窗口基于 cursor。

#### Scenario: 构建查询
- **WHEN** 配置 topics=["llm","ai"], languages=["python"], cursor="2026-04-12T00:00:00Z"
- **THEN** 查询为 `topic:llm topic:ai language:python created:>2026-04-12T00:00:00Z stars:>50&sort=stars&order=desc`

#### Scenario: 首次拉取
- **WHEN** fetch_log 中无 github 记录
- **THEN** 查询最近 7 天内创建的、stars >= min_stars 的仓库

#### Scenario: API 返回空结果
- **WHEN** 查询返回 total_count=0
- **THEN** 系统记录日志 "GitHub Trending: 无新仓库符合条件"，不报错

### Requirement: GitHub 数据规范化
GitHub Fetcher SHALL 将每个仓库规范化为 Article 字典：url (html_url)、title (full_name: description)、content_raw (description + topic 列表)、source="github"、source_name="GitHub Trending"、author (owner.login)、published_at (created_at)、platform_score (stargazers_count)。

#### Scenario: 规范化仓库
- **WHEN** 拉取到一个仓库（full_name="user/awesome-llm", description="A curated list of LLM resources", stargazers_count=1200, language="Python"）
- **THEN** 规范化结果 source="github", source_name="GitHub Trending", platform_score=1200, title="user/awesome-llm: A curated list of LLM resources"

#### Scenario: 仓库无 description
- **WHEN** 仓库 description 为 null
- **THEN** title 使用 full_name，content_raw 包含 topic 列表和 language 信息

### Requirement: GitHub 增量拉取
GitHub Fetcher SHALL 使用 fetch_log cursor 实现增量拉取。cursor 记录 `last_created_at`（ISO 时间戳）。

#### Scenario: 增量拉取
- **WHEN** fetch_log 中 github cursor 为 "2026-04-12T10:00:00Z"
- **THEN** 只查询 created_at > "2026-04-12T10:00:00Z" 的仓库

#### Scenario: 更新 cursor
- **WHEN** 拉取完成后，最新仓库的 created_at 为 "2026-04-13T08:30:00Z"
- **THEN** cursor 更新为 "2026-04-13T08:30:00Z"

### Requirement: GitHub 速率感知
GitHub Fetcher SHALL 检查响应头中的速率限制信息，在接近限制时暂停或降频。

#### Scenario: 速率充足
- **WHEN** X-RateLimit-Remaining > 10
- **THEN** 正常拉取，无延迟

#### Scenario: 速率即将耗尽
- **WHEN** X-RateLimit-Remaining <= 5
- **THEN** 系统记录警告日志，暂停拉取直到 X-RateLimit-Reset 时间

#### Scenario: 速率已耗尽
- **WHEN** API 返回 HTTP 403 且 X-RateLimit-Remaining=0
- **THEN** 系统等待 reset 时间后重试，或提前终止本次拉取并记录已拉取的数据

### Requirement: GitHub 分页处理
GitHub Search API 单次最多返回 100 条结果，GitHub Fetcher SHALL 支持分页拉取。

#### Scenario: 结果超过 100 条
- **WHEN** 查询匹配 250 个仓库
- **THEN** 系统分 3 页拉取（per_page=100），合并所有结果

#### Scenario: 分页拉取限制
- **WHEN** 匹配结果超过 1000 条（GitHub Search API 上限）
- **THEN** 系统只拉取前 1000 条并记录日志说明

### Requirement: CLI sources add github-trending
系统 SHALL 支持 `ainews sources add github-trending` 命令，可选参数 --topic、--language、--min-stars、--token。

#### Scenario: 添加 GitHub Trending 源
- **WHEN** 用户运行 `ainews sources add github-trending --topic ai --min-stars 100`
- **THEN** 配置文件中 sources.github.topics 包含 "ai"，min_stars 设为 100

#### Scenario: 配置 PAT
- **WHEN** 用户运行 `ainews sources add github-trending --token ghp_xxx`
- **THEN** token 写入配置（标记为敏感字段），后续请求使用认证模式

### Requirement: CLI sources test github-trending
系统 SHALL 支持 `ainews sources test github-trending` 命令，验证 GitHub API 连通性和认证状态。

#### Scenario: 测试成功（已认证）
- **WHEN** 用户运行 `ainews sources test github-trending` 且 PAT 有效
- **THEN** 显示连接成功、认证用户名、速率限制余量（5000 req/h）

#### Scenario: 测试成功（未认证）
- **WHEN** 用户运行 `ainews sources test github-trending` 且无 PAT
- **THEN** 显示连接成功、未认证模式、速率限制余量（60 req/h），提示建议配置 PAT

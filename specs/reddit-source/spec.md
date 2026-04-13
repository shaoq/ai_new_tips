## ADDED Requirements

### Requirement: Reddit 配置模型
系统 SHALL 在配置中支持 Reddit 分组，包含以下字段：enabled (BOOL)、client_id (TEXT)、client_secret (TEXT)、user_agent (TEXT)、subreddits (LIST)、fetch_interval_minutes (INT, 默认 30)。client_id 和 client_secret 标记为敏感字段。

#### Scenario: Reddit 配置完整加载
- **WHEN** 系统读取包含 `sources.reddit` 完整配置的 config.yaml
- **THEN** Reddit 配置正确解析，subreddits 列表包含 MachineLearning、LocalLLaMA、ChatGPT

#### Scenario: Reddit 凭证缺失
- **WHEN** Reddit 配置中 client_id 或 client_secret 为空且 enabled 为 true
- **THEN** 系统在 `ainews doctor` 检查中报告 Reddit 配置不完整

### Requirement: Reddit OAuth2 认证
Reddit Fetcher SHALL 使用 PRAW 库通过 OAuth2 认证连接 Reddit API。认证失败时 SHALL 抛出明确错误信息，指导用户检查凭证。

#### Scenario: 认证成功
- **WHEN** 系统使用有效的 client_id 和 client_secret 创建 PRAW 实例
- **THEN** 成功连接 Reddit API，可查询 subreddit 帖子

#### Scenario: 认证失败
- **WHEN** 系统使用无效的 client_id 或 client_secret
- **THEN** 抛出 FetcherAuthError，提示 "Reddit OAuth2 认证失败，请检查 client_id 和 client_secret 配置"

### Requirement: Reddit 帖子拉取
Reddit Fetcher SHALL 从配置的 subreddit 列表拉取帖子。每个 subreddit 拉取 hot 排序的帖子，支持 AI 关键词过滤。

#### Scenario: 拉取多 subreddit
- **WHEN** 配置了 MachineLearning、LocalLLaMA、ChatGPT 三个 subreddit
- **THEN** 系统依次拉取每个 subreddit 的帖子，所有结果合并返回

#### Scenario: AI 关键词过滤
- **WHEN** 拉取到的帖子标题为 "Best hiking trails in Europe"
- **THEN** 该帖子被过滤掉，不进入后续处理

#### Scenario: 拉取 AI 相关帖子
- **WHEN** 拉取到的帖子标题为 "New transformer architecture achieves SOTA on GLUE"
- **THEN** 该帖子通过 AI 关键词过滤，进入后续处理

### Requirement: Reddit 增量拉取
Reddit Fetcher SHALL 使用 fetch_log cursor 实现增量拉取。cursor 记录 `last_post_timestamp`，每次只拉取该时间戳之后的帖子。

#### Scenario: 首次拉取（无 cursor）
- **WHEN** fetch_log 中无 reddit 记录
- **THEN** 拉取各 subreddit 当前 hot 帖子，cursor 设为最新帖子时间戳

#### Scenario: 增量拉取
- **WHEN** fetch_log 中 reddit cursor 为 "2026-04-13T10:00:00Z"
- **THEN** 只拉取 2026-04-13T10:00:00Z 之后的新帖子

### Requirement: Reddit 数据规范化
Reddit Fetcher SHALL 将每个 Submission 规范化为 Article 字典：url (permalink)、title、content_raw (selftext)、source="reddit"、source_name="r/{subreddit}"、author (author.name)、published_at (created_utc)、platform_score (score)、comment_count (num_comments)。

#### Scenario: 规范化帖子
- **WHEN** 拉取到一篇 r/MachineLearning 帖子（title="New paper on RAG", score=243, num_comments=56）
- **THEN** 规范化结果 source="reddit", source_name="r/MachineLearning", platform_score=243, comment_count=56

#### Scenario: 自链接帖子（link post）
- **WHEN** 帖子是链接类型（非 selftext），外部 URL 指向 arxiv.org
- **THEN** url 使用外部链接（arxiv.org），content_raw 为空或包含 Reddit 讨论页内容

### Requirement: Reddit 速率限制处理
Reddit Fetcher SHALL 遵守 PRAW 的速率限制（100 req/min），在接近限制时自动退避。

#### Scenario: 速率正常
- **WHEN** API 调用次数远低于 100 req/min 限制
- **THEN** 正常拉取，无延迟

#### Scenario: 接近速率限制
- **WHEN** PRAW 报告接近速率限制
- **THEN** 自动插入延迟，等待速率窗口恢复后继续

### Requirement: CLI sources add reddit
系统 SHALL 支持 `ainews sources add reddit --subreddit <name>` 命令，将 subreddit 添加到配置的 subreddits 列表。

#### Scenario: 添加新 subreddit
- **WHEN** 用户运行 `ainews sources add reddit --subreddit MachineLearning`
- **THEN** 配置文件 sources.reddit.subreddits 新增 "MachineLearning"，如果 reddit 配置不存在则创建

#### Scenario: 重复添加
- **WHEN** 用户运行 `ainews sources add reddit --subreddit MachineLearning` 但该 subreddit 已在列表中
- **THEN** 系统提示该 subreddit 已存在，不做重复添加

### Requirement: CLI sources test reddit
系统 SHALL 支持 `ainews sources test reddit` 命令，验证 Reddit API 连通性和凭证有效性。

#### Scenario: 测试成功
- **WHEN** 用户运行 `ainews sources test reddit` 且凭证有效
- **THEN** 显示连接成功、当前速率限制余量、监控的 subreddit 列表

#### Scenario: 凭证无效
- **WHEN** 用户运行 `ainews sources test reddit` 且凭证无效
- **THEN** 显示连接失败原因和修复建议

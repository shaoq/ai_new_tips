## ADDED Requirements

### Requirement: 中文源配置模型
系统 SHALL 在配置中支持 Chinese 分组，包含以下字段：enabled (BOOL, 默认 true)、sources (LIST)、fetch_interval_minutes (INT, 默认 60)。sources 列表中每项包含 name (TEXT)、url (TEXT)、method ("rss" 或 "scrape")。

#### Scenario: 配置加载
- **WHEN** 系统读取包含 `sources.chinese` 配置的 config.yaml
- **THEN** Chinese 配置正确解析，sources 列表包含 qbitai、jiqizhixin、aibase 三个源

#### Scenario: 单个源禁用
- **WHEN** 用户只想监控 量子位 和 机器之心，不想监控 AIbase
- **THEN** 配置 sources 列表中只包含 qbitai 和 jiqizhixin，aibase 不在其中

### Requirement: RSS 模式解析
中文源 Fetcher SHALL 使用 feedparser 解析 RSS feed，提取文章标题、链接、发布时间、内容摘要。

#### Scenario: 解析量子位 RSS
- **WHEN** 量子位配置 method=rss，RSS feed 返回 10 篇文章
- **THEN** 系统提取每篇文章的 title、link、published、summary 字段

#### Scenario: RSS feed 格式不规范
- **WHEN** RSS feed 中某些条目缺少 published 字段
- **THEN** 系统使用 fetched_at 时间作为 fallback，记录警告日志

#### Scenario: RSS feed 无法访问
- **WHEN** RSS feed URL 返回 HTTP 错误或超时
- **THEN** 如果该源同时配置了 scrape 方法对应的 URL，自动降级到 scrape 模式；否则记录错误并跳过该源

### Requirement: Scrape 模式解析
中文源 Fetcher SHALL 使用 httpx + BeautifulSoup 解析网页 HTML，通过源特定的 CSS 选择器提取文章列表。

#### Scenario: 解析 AIbase 网页
- **WHEN** AIbase 配置 method=scrape，网页返回文章列表 HTML
- **THEN** 系统使用预定义的 CSS 选择器提取文章列表（标题、链接、时间、摘要）

#### Scenario: 网页结构变化导致选择器失效
- **WHEN** AIbase 网页改版，预定义的 CSS 选择器匹配不到元素
- **THEN** 系统记录警告日志 "AIbase: 网页结构可能已变化，CSS 选择器未匹配到内容"，返回空列表（不抛异常）

#### Scenario: 网页编码处理
- **WHEN** 网页使用 GBK 或其他非 UTF-8 编码
- **THEN** BeautifulSoup 自动检测编码，正确解析中文内容

### Requirement: 中文源数据规范化
中文源 Fetcher SHALL 将每篇解析到的文章规范化为 Article 字典：url、title、content_raw（摘要或正文片段）、source="chinese"、source_name（源名称如 "qbitai"、"jiqizhixin"、"aibase"）、author（如可提取）、published_at。

#### Scenario: 规范化量子位文章
- **WHEN** 从量子位解析到一篇文章（title="OpenAI 发布 GPT-6", summary="..."）
- **THEN** 规范化结果 source="chinese", source_name="qbitai"

#### Scenario: URL 重复检测
- **WHEN** 同一篇量子位文章在 RSS 和网页解析中都被提取到
- **THEN** 通过 url_hash 去重，只保留一条记录

### Requirement: 中文源增量拉取
中文源 Fetcher SHALL 使用 fetch_log cursor 实现增量拉取。cursor 记录 `last_item_timestamp`，每个中文源独立维护。

#### Scenario: 首次拉取
- **WHEN** fetch_log 中无 chinese 记录
- **THEN** 拉取所有源的最新文章，cursor 设为各源最新文章时间戳的最大值

#### Scenario: 增量拉取
- **WHEN** fetch_log 中 chinese cursor 为 "2026-04-13T08:00:00Z"
- **THEN** 各源只拉取 published_at > "2026-04-13T08:00:00Z" 的文章

### Requirement: 中文源容错
中文源 Fetcher SHALL 保证单个源解析失败不影响其他源的拉取。

#### Scenario: 一个源失败
- **WHEN** 量子位 RSS 解析失败，但机器之心和 AIbase 解析成功
- **THEN** 系统记录量子位失败日志（包含错误详情），返回机器之心和 AIbase 的数据

#### Scenario: 所有源失败
- **WHEN** 三个中文源全部解析失败
- **THEN** 系统返回空列表，记录各源的失败原因，不抛异常阻断整个 fetch 流程

### Requirement: 中文源 AI 关键词过滤
中文源 Fetcher SHALL 对文章标题应用 AI 关键词过滤，只保留与 AI/机器学习相关的内容。

#### Scenario: 过滤非 AI 文章
- **WHEN** 解析到一篇文章标题为 "新能源汽车销量创历史新高"
- **THEN** 该文章被过滤掉

#### Scenario: 保留 AI 文章
- **WHEN** 解析到一篇文章标题为 "OpenAI 发布最新大模型 GPT-6"
- **THEN** 该文章通过过滤，进入后续处理

#### Scenario: 中文 AI 关键词列表
- **WHEN** 系统初始化中文源 Fetcher
- **THEN** 加载中文 AI 关键词列表：AI、人工智能、大模型、LLM、GPT、Claude、Gemini、机器学习、深度学习、神经网络、transformer、AGI、ChatGPT、OpenAI、Anthropic、DeepMind、计算机视觉、NLP、生成式、微调、RAG、Agent、多模态 等

### Requirement: CLI sources add chinese
系统 SHALL 支持 `ainews sources add chinese --name <name> --url <url> --method <rss|scrape>` 命令。

#### Scenario: 添加中文 RSS 源
- **WHEN** 用户运行 `ainews sources add chinese --name qbitai --url https://www.qbitai.com/feed --method rss`
- **THEN** 配置文件 sources.chinese.sources 新增 {name: "qbitai", url: "https://www.qbitai.com/feed", method: "rss"}

#### Scenario: 添加重复源
- **WHEN** 用户运行 `ainews sources add chinese --name qbitai` 但 qbitai 已在列表中
- **THEN** 系统提示该源已存在，不做重复添加

### Requirement: CLI sources test chinese
系统 SHALL 支持 `ainews sources test chinese` 命令，验证各中文源的连通性。

#### Scenario: 测试所有中文源
- **WHEN** 用户运行 `ainews sources test chinese`
- **THEN** 依次测试每个配置的中文源，显示各源状态（可达/不可达、RSS 解析/网页解析模式、最近文章数）

#### Scenario: 测试单个中文源
- **WHEN** 用户运行 `ainews sources test chinese --name qbitai`
- **THEN** 只测试量子位源，显示连通性和最近文章标题

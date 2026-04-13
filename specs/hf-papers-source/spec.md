## ADDED Requirements

### Requirement: HuggingFace Papers 配置模型
系统 SHALL 在配置中支持 HuggingFace Papers 分组，包含以下字段：enabled (BOOL, 默认 true)、fetch_interval_minutes (INT, 默认 360)、min_upvotes (INT, 默认 10)。

#### Scenario: 配置加载
- **WHEN** 系统读取包含 `sources.hf_papers` 配置的 config.yaml
- **THEN** HFPapers 配置正确解析，min_upvotes 默认为 10，fetch_interval_minutes 默认为 360

#### Scenario: 配置缺失使用默认值
- **WHEN** config.yaml 中不包含 hf_papers 配置
- **THEN** 系统使用默认值 enabled=true、min_upvotes=10、fetch_interval_minutes=360

### Requirement: HuggingFace Papers API 调用
HFPapers Fetcher SHALL 使用 httpx 调用 `https://huggingface.co/api/daily_papers` 端点获取每日精选论文。无需认证。

#### Scenario: 拉取今日论文
- **WHEN** 系统调用 `GET /api/daily_papers?date=2026-04-13`
- **THEN** 返回当日精选论文列表，每篇包含 id、title、authors、abstract、upvotes、publishedAt、arxiv 链接

#### Scenario: API 返回空结果
- **WHEN** 某日无精选论文（API 返回空列表）
- **THEN** 系统记录日志 "HuggingFace Papers: 今日无精选论文"，不报错

### Requirement: HuggingFace Papers upvotes 过滤
HFPapers Fetcher SHALL 根据 min_upvotes 配置过滤论文，只保留达到阈值的论文。

#### Scenario: 过滤低 upvotes 论文
- **WHEN** min_upvotes=10，拉取到的论文中 upvotes 分别为 5、15、120、3
- **THEN** 只保留 upvotes=15 和 upvotes=120 的论文

#### Scenario: 所有论文都达标
- **WHEN** min_upvotes=10，所有论文 upvotes 均 > 10
- **THEN** 保留所有论文

### Requirement: HuggingFace Papers 数据规范化
HFPapers Fetcher SHALL 将每篇论文规范化为 Article 字典：url (论文页面链接)、title、content_raw (abstract)、source="hf_papers"、source_name="HuggingFace Papers"、author (authors 列表，逗号分隔)、published_at (publishedAt)、platform_score (upvotes)。

#### Scenario: 规范化论文
- **WHEN** 拉取到一篇论文（title="Attention Is All You Need 2.0", upvotes=89, authors=["Author A", "Author B"]）
- **THEN** 规范化结果 source="hf_papers", source_name="HuggingFace Papers", platform_score=89, author="Author A, Author B"

#### Scenario: 论文含 ArXiv 链接
- **WHEN** 论文数据包含 arxiv_id="2401.12345"
- **THEN** url 使用 `https://arxiv.org/abs/2401.12345`，同时记录 HF 页面链接在 content_raw 中

### Requirement: HuggingFace Papers 增量拉取
HFPapers Fetcher SHALL 使用 fetch_log cursor 实现增量拉取。cursor 记录 `last_date`（ISO 日期字符串）。

#### Scenario: 首次拉取
- **WHEN** fetch_log 中无 hf_papers 记录
- **THEN** 拉取当日论文，cursor 设为当日日期

#### Scenario: 增量拉取
- **WHEN** fetch_log 中 hf_papers cursor 为 "2026-04-12"
- **THEN** 拉取 2026-04-13（今天）的论文，跳过 cursor 日期及之前的

#### Scenario: 回溯拉取
- **WHEN** 用户运行 `ainews fetch --source hf-papers --backfill 7d`
- **THEN** 拉取最近 7 天的 daily_papers，从 (today - 7d) 到 today

### Requirement: HuggingFace Papers 限速
HFPapers Fetcher SHALL 自限速率为 1 req/2s，并监控 HTTP 429 响应码。

#### Scenario: 正常请求
- **WHEN** 连续调用 API 但保持 1 req/2s 节奏
- **THEN** 正常获取数据，无延迟

#### Scenario: 收到 429 响应
- **WHEN** API 返回 HTTP 429 Too Many Requests
- **THEN** 系统等待 Retry-After 头指定的时间后重试，最多重试 3 次

### Requirement: CLI sources add hf-papers
系统 SHALL 支持 `ainews sources add hf-papers` 命令，可选参数 --min-upvotes。

#### Scenario: 添加 HF Papers 源
- **WHEN** 用户运行 `ainews sources add hf-papers`
- **THEN** 配置文件中 sources.hf_papers.enabled 设为 true

#### Scenario: 自定义 upvotes 阈值
- **WHEN** 用户运行 `ainews sources add hf-papers --min-upvotes 50`
- **THEN** 配置文件中 sources.hf_papers.min_upvotes 设为 50

### Requirement: CLI sources test hf-papers
系统 SHALL 支持 `ainews sources test hf-papers` 命令，验证 HuggingFace API 连通性。

#### Scenario: 测试成功
- **WHEN** 用户运行 `ainews sources test hf-papers`
- **THEN** 显示连接成功、今日论文数量、最近一篇论文标题

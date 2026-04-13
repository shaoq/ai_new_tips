## 1. BaseFetcher 框架

- [x] 1.1 实现 `ainews/fetcher/base.py`：`BaseFetcher` 抽象基类，定义 `fetch()`、`fetch_items()`（抽象）、`test_connection()`、`_load_cursor()`、`_update_cursor()`、`_dedup_by_url()`、`_save_articles()` 方法
- [x] 1.2 实现增量水印管理：`_load_cursor()` 从 fetch_log 读取 source 对应的 cursor，`_update_cursor()` 写回 last_fetch_at、cursor、items_fetched
- [x] 1.3 实现 URL 去重：`_dedup_by_url()` 计算 URL SHA256，批量查询 articles.url_hash，过滤已存在的 URL
- [x] 1.4 实现批量入库：`_save_articles()` 将去重后的 Article 列表批量插入 articles 表，设置 fetched_at、status='unread'、processed=False

## 2. HackerNews 采集器

- [x] 2.1 实现 `ainews/fetcher/hackernews.py`：`HackerNewsFetcher(BaseFetcher)`，使用 httpx 调用 Firebase API
- [x] 2.2 实现 Firebase API 集成：获取 topstories/newstories ID 列表，批量获取 item 详情（score、title、url、time、kids）
- [x] 2.3 实现 Algolia API 集成：搜索接口带 AI 关键词 + 时间范围 + points 过滤，用于回填场景
- [x] 2.4 实现 AI 关键词过滤：标题匹配 AI_KEYWORDS 列表，过滤非 AI 相关内容
- [x] 2.5 实现增量水印：使用 `last_item_timestamp` 作为 cursor，只拉取上次采集后的新 item
- [x] 2.6 实现 source_metrics 记录：将 HN score、comment_count 写入 source_metrics 表

## 3. ArXiv 采集器

- [x] 3.1 实现 `ainews/fetcher/arxiv.py`：`ArXivFetcher(BaseFetcher)`，使用 httpx 调用 ArXiv API
- [x] 3.2 实现 Atom XML 解析：解析 ArXiv API 返回的 Atom feed，提取 title、summary、authors、published、link、categories
- [x] 3.3 实现分类过滤：默认监控 cs.AI、cs.LG、cs.CL，可通过配置修改
- [x] 3.4 实现速率限制：请求间 sleep 3 秒，确保遵守 ArXiv API 使用条款
- [x] 3.5 实现增量水印：使用 `last_submit_date` 作为 cursor，sortBy=submittedDate 降序
- [x] 3.6 实现分页拉取：支持 start/max_results 参数，处理多页结果

## 4. RSS/Atom 采集器

- [x] 4.1 实现 `ainews/fetcher/rss.py`：`RSSFetcher(BaseFetcher)`，使用 feedparser 解析 feed
- [x] 4.2 实现多源管理：从配置文件读取 RSS 源列表，支持动态添加/删除源
- [x] 4.3 实现 HTTP 条件请求：发送 ETag / If-Modified-Since 头，处理 304 Not Modified 响应
- [x] 4.4 实现 ETag/Last-Modified 水印：将 etag 和 last_modified 存入 fetch_log.cursor（JSON 格式）
- [x] 4.5 实现降级策略：对不支持 ETag 的源，使用文章发布时间作为水印过滤
- [x] 4.6 实现默认 RSS 源列表：预配置 OpenAI Blog、DeepMind、Anthropic、Meta AI、HuggingFace Blog 等核心 AI 博客

## 5. 采集编排

- [x] 5.1 实现 `ainews/fetcher/registry.py`：Fetcher 注册表，维护 source_name → FetcherClass 的映射，支持动态注册
- [x] 5.2 实现 `ainews/fetcher/runner.py`：采集编排器，根据 CLI 参数选择源（全部/指定），依次执行 fetch，汇总结果统计

## 6. CLI 命令

- [x] 6.1 实现 `ainews/cli/fetch.py`：`ainews fetch` 命令，支持 `--source`（指定源，逗号分隔）、`--backfill`（回填天数）、`--force`（忽略水印）、`--dry-run`（预览模式）
- [x] 6.2 实现 `ainews/cli/sources.py`：`ainews sources list`（列出所有源及状态）、`sources add`（添加源）、`sources remove`（移除源）、`sources enable`（启用源）、`sources disable`（禁用源）、`sources test`（测试源连通性）
- [x] 6.3 注册新命令到 `ainews/cli/main.py` 主应用

## 7. 测试

- [x] 7.1 测试 BaseFetcher：水印读写、URL 去重、批量入库（`tests/test_fetcher_base.py`，使用 mock 数据库）
- [x] 7.2 测试 HackerNews 采集器：Firebase/Algolia API 解析、AI 关键词过滤、增量逻辑（`tests/test_fetcher_hackernews.py`，mock HTTP 响应）
- [x] 7.3 测试 ArXiv 采集器：Atom XML 解析、分类过滤、速率限制（`tests/test_fetcher_arxiv.py`，mock API 响应）
- [x] 7.4 测试 RSS 采集器：feedparser 集成、ETag/Last-Modified 水印、降级策略（`tests/test_fetcher_rss.py`，mock feed 数据）
- [x] 7.5 测试 CLI 命令：fetch 和 sources 子命令的参数解析和执行（`tests/test_cli_fetch.py`）
- [x] 7.6 确认测试覆盖率 >= 80%（实测 87%）

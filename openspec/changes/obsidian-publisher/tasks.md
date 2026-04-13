## 1. Obsidian REST API 客户端

- [x] 1.1 实现 `ainews/publisher/obsidian_client.py`：ObsidianClient 类，封装 httpx 客户端，配置 base_url（`https://127.0.0.1:{port}`）、Bearer 认证头、`verify=False`、超时 10s
- [x] 1.2 实现连接健康检查：`health_check()` 调用 `GET /`，返回连接状态，失败时日志记录
- [x] 1.3 实现文件系统降级：当健康检查失败时，切换为直接写入 `vault_path` 目录模式，记录降级事件日志
- [x] 1.4 实现 REST API 操作封装：`put_vault_file(path, content)`、`patch_periodic_daily(heading, content)`、`patch_frontmatter(path, fields)`、`search_simple(query)`、`get_vault_file(path)`
- [x] 1.5 实现请求重试：对连接错误和 5xx 响应重试最多 3 次，指数退避（1s/2s/4s）

## 2. Markdown 模板渲染

- [x] 2.1 实现 `ainews/publisher/obsidian_templates.py`：`render_article_frontmatter(article)` 生成 YAML frontmatter（title/date/source/source_name/author/tags/category/status/relevance/trend_score/is_trending/summary/platforms/entities/imported_at/dingtalk_sent）
- [x] 2.2 实现 `render_article_body(article)` 生成 Markdown 正文（中文摘要 + 原文链接 + `[[双链]]` 关联实体）
- [x] 2.3 实现 `render_daily_section(articles, timestamp)` 生成 `## HH:MM 更新 (N篇)` 段落
- [x] 2.4 实现 `render_daily_header()` 生成每日笔记头部（标题 + Dataview 概览表）
- [x] 2.5 实现 `render_entity_page(entity, articles)` 生成实体页面（类型/首次出现/提及次数/相关文章 Dataview 查询）
- [x] 2.6 实现 8 个仪表盘模板渲染函数：Home、Trending、Daily-Stats、Weekly-Stats、Reading-List、People-Tracker、Knowledge-Graph、By-Category

## 3. 文章同步

- [x] 3.1 实现 `ainews/publisher/article_sync.py`：`sync_articles()` 查询 `obsidian_synced = false` 的文章，按分类排序
- [x] 3.2 实现 slug 生成：标题转小写、移除特殊字符、空格转连字符、截断 60 字符
- [x] 3.3 实现 REST API 模式文章写入：调用 `PUT /vault/AI-News/{category}/{date-slug}.md`
- [x] 3.4 实现文件系统降级模式文章写入：创建目录（如不存在）、写入 `.md` 文件
- [x] 3.5 实现已同步文章的 frontmatter 更新：当文章已存在但字段变更时（如 trend_score 更新），通过 `PATCH` 更新 frontmatter
- [x] 3.6 实现同步成功标记：更新数据库 `articles.obsidian_synced = true`，记录 `obsidian_path`

## 4. 每日笔记

- [x] 4.1 实现 `ainews/publisher/daily_note.py`：`sync_daily_note(articles)` 追加文章摘要到当日 daily note
- [x] 4.2 实现 REST API 模式每日笔记：调用 `PATCH /periodic/daily/` + `Target-Type: heading` + `Operation: append`
- [x] 4.3 实现文件系统降级模式每日笔记：追加到 `AI-News/Daily/{YYYY-MM-DD}.md`，文件不存在时创建并写入头部
- [x] 4.4 实现每日笔记头部：标题 `# AI News - {date}` + Dataview 概览表

## 5. 实体页面

- [x] 5.1 实现 `ainews/publisher/entity_pages.py`：`sync_entity_pages()` 查询数据库中所有实体及其关联文章
- [x] 5.2 实现 REST API 模式实体页面：先通过 `POST /search/simple/` 检查页面是否存在，不存在则 `PUT` 创建，存在则 `PATCH` 更新 frontmatter
- [x] 5.3 实现文件系统降级模式实体页面：检查文件存在性，创建或更新
- [x] 5.4 实现实体页面 frontmatter 更新：mention_count 递增、last_seen 更新、related_articles 列表更新
- [x] 5.5 实现实体文件名规范化：空格转连字符、特殊字符移除（如 `Sam Altman` -> `Sam-Altman.md`）

## 6. 仪表盘初始化

- [x] 6.1 实现 `ainews/publisher/dashboards.py`：`init_dashboards()` 创建 8 个仪表盘文件到 `AI-News/Dashboards/`
- [x] 6.2 实现 Dashboard 模板内容：Home（总览 + 今日概览 + 7 天趋势）、Trending（48h 热点 + 跨平台热点）、Daily-Stats（来源分布 + 分类分布）、Weekly-Stats（周统计）、Reading-List（未读列表 + 本周未读热点）、People-Tracker（活跃度 Top 20 + 新发现）、Knowledge-Graph（实体列表 + Graph View 入口）、By-Category（分类视图）
- [x] 6.3 实现 `rebuild_dashboards()` 逻辑：覆盖已有仪表盘文件，用于模板升级

## 7. CLI 命令

- [x] 7.1 实现 `ainews/cli/sync.py`：注册 `ainews sync obsidian` 子命令，支持 `--test`、`--init-dashboards`、`--sync-entities`、`--rebuild-dashboards` 选项
- [x] 7.2 实现 `--test` 模式：执行连接健康检查，验证配置（vault_path 存在、API key 非空），输出检查结果
- [x] 7.3 实现 `--init-dashboards` 模式：调用 `init_dashboards()` 创建仪表盘模板
- [x] 7.4 实现 `--sync-entities` 模式：调用 `sync_entity_pages()` 同步实体页面
- [x] 7.5 实现默认模式（无选项）：执行完整同步（文章 -> 每日笔记 -> 实体页面）
- [x] 7.6 注册 sync 子命令到 CLI 主入口

## 8. 测试

- [x] 8.1 测试 ObsidianClient：健康检查、降级、重试、REST API 操作（使用 httpx mock，`tests/test_obsidian_client.py`）
- [x] 8.2 测试模板渲染：frontmatter 生成、Markdown 正文、每日笔记段落、实体页面、仪表盘（`tests/test_obsidian_templates.py`）
- [x] 8.3 测试文章同步：slug 生成、REST API 写入、文件系统降级、幂等性、frontmatter 更新（`tests/test_article_sync.py`）
- [x] 8.4 测试每日笔记：追加段落、头部生成、降级模式（`tests/test_daily_note.py`）
- [x] 8.5 测试实体页面：创建/更新、文件名规范化、重复检查（`tests/test_entity_pages.py`）
- [x] 8.6 测试 CLI 命令：`sync obsidian --test/--init-dashboards/--sync-entities`、默认模式（`tests/test_sync_cli.py`，使用 typer.testing.CliRunner）
- [x] 8.7 确认测试覆盖率 >= 80%

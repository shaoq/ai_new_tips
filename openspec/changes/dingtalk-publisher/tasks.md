## 1. 钉钉 Webhook 客户端

- [x] 1.1 实现 `ainews/publisher/dingtalk.py`：`sign_dingtalk(secret)` 函数，计算 HMAC-SHA256 签名（timestamp + "\n" + secret -> HMAC-SHA256 -> base64 -> URL encode）
- [x] 1.2 实现 `DingTalkClient` 类：`__init__` 接收 webhook_url 和 secret，`send(message: dict)` 方法拼接签名 URL 并 POST 请求
- [x] 1.3 实现响应处理：解析钉钉 JSON 响应，检查 errcode（0 为成功），非 0 时抛出包含 errmsg 的异常
- [x] 1.4 实现重试机制：5xx 或网络错误时指数退避重试（最多 3 次，间隔 1s/2s/4s），4xx 不重试
- [x] 1.5 实现令牌桶限流器：20 令牌/分钟容量，`acquire()` 方法在发送前检查，超出时等待至令牌可用

## 2. 消息格式构建器

- [x] 2.1 实现 `ainews/publisher/formatter.py`：`build_feedcard(articles, title)` 函数，构建 feedCard 消息体（包含 title、messageURL、picURL 的 links 数组）
- [x] 2.2 实现 `build_actioncard(article)` 函数，构建 actionCard 消息体（包含 title、markdown text、两个按钮：阅读原文、查看 Obsidian）
- [x] 2.3 实现 `build_markdown_weekly(stats, top_articles)` 函数，构建周报 markdown 消息（本周数据统计 + Top 5 热点 + 分类分布）
- [x] 2.4 实现 `build_markdown_noon(articles)` 函数，构建午间速报 markdown 消息（热点列表 + 阅读原文链接 + 当日累计统计）
- [x] 2.5 实现 `build_test_message()` 函数，构建测试消息（简单的 markdown 文本，用于 `--test` 选项验证连接）

## 3. 推送策略引擎

- [x] 3.1 实现 `ainews/publisher/strategy.py`：`PushStrategy` 类，`should_push(article, push_type)` 方法判断是否推送（检查 dingtalk_sent、trend_score 阈值、推送类型条件）
- [x] 3.2 实现去重查询：查询 push_log 表判断文章在指定 push_type 下是否已推送，feedCard 去重按 article 粒度，actionCard 允许对同一文章的即时热点单独推送
- [x] 3.3 实现每日即时推送计数器：查询 push_log 表当天 push_type='actioncard' 的记录数，上限 3 条
- [x] 3.4 实现午间推送跳过逻辑：当无 trend_score >= 8 的新热点文章时，`should_skip_noon()` 返回 True
- [x] 3.5 实现文章查询函数：按推送模式从数据库查询符合条件的文章（morning_digest: Top 10 by trend_score; evening_digest: 全部增量 by fetched_at; noon_update: trend_score >= 8）

## 4. CLI 命令

- [x] 4.1 实现 `ainews/cli/push.py`：`push` 子命令组，注册 `dingtalk` 子命令
- [x] 4.2 实现 `ainews push dingtalk` 默认模式：查询未推送文章，按当前时间段自动选择推送格式（08:00 feedCard / 12:30 markdown / 20:00 feedCard）
- [x] 4.3 实现 `--trending-only` 选项：仅推送 trend_score >= 8 的热点文章
- [x] 4.4 实现 `--weekly` 选项：生成本周统计并推送周报 markdown
- [x] 4.5 实现 `--test` 选项：发送测试消息验证 Webhook 连通性
- [x] 4.6 实现 `--format feedcard|markdown` 选项：强制指定消息格式
- [x] 4.7 实现 `--article <slug>` 选项：推送指定单篇文章
- [x] 4.8 在 `ainews/cli/main.py` 中注册 push 命令组

## 5. 推送记录与状态更新

- [x] 5.1 实现推送成功后写入 push_log 表：记录 article_id、push_type、msg_id、pushed_at
- [x] 5.2 实现推送成功后更新 articles.dingtalk_sent = True
- [x] 5.3 实现推送失败时的日志记录：包含 article 信息、错误详情，不更新 dingtalk_sent 状态

## 6. 测试

- [x] 6.1 测试签名计算：验证 timestamp + secret -> HMAC-SHA256 -> base64 -> URL encode 的正确性（`tests/test_dingtalk_client.py`）
- [x] 6.2 测试消息格式构建器：验证 feedCard/actionCard/markdown 消息体结构符合钉钉 API 规范（`tests/test_message_formatter.py`）
- [x] 6.3 测试推送策略：去重判断、每日上限、午间跳过、trend_score 阈值过滤（`tests/test_push_strategy.py`）
- [x] 6.4 测试 CLI 命令：push dingtalk 各选项的行为，使用 mock 替代真实 HTTP 请求（`tests/test_cli_push.py`）
- [x] 6.5 确认测试覆盖率 >= 80%

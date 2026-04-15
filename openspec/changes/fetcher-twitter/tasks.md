## 1. 配置层

- [x] 1.1 在 `ainews/config/settings.py` 中新增 `TwitterConfig` 配置类（enabled, api_key, accounts, search_queries, min_engagement, fetch_interval_minutes）
- [x] 1.2 在 `SourcesConfig` 中新增 `twitter: TwitterConfig = TwitterConfig()` 字段
- [x] 1.3 在 `AppConfig.mask_secrets()` 中新增 `twitter.api_key` 脱敏处理

## 2. 核心 Fetcher 实现

- [x] 2.1 新建 `ainews/fetcher/twitter.py`，实现 `TwitterFetcher` 类继承 `BaseFetcher`
- [x] 2.2 实现 `_init_http_client()` 方法，初始化 httpx.AsyncClient 或 httpx.Client（Bearer Token 认证）
- [x] 2.3 实现 `_resolve_user_id()` 方法，将 screen_name 解析为 user_id 并缓存
- [x] 2.4 实现 `_fetch_account_tweets()` 方法，调用 `/twitter/user/{user_id}/tweets` 拉取账户推文
- [x] 2.5 实现 `_fetch_search_tweets()` 方法，调用 `/twitter/search` 搜索热门推文
- [x] 2.6 实现 `_normalize_tweet()` 方法，将 API 返回 JSON 标准化为统一条目格式
- [x] 2.7 实现 `_filter_tweet()` 方法，过滤回复、转推、短文本、低互动量推文
- [x] 2.8 实现 `fetch_items()` 方法，合并账户模式和搜索模式结果
- [x] 2.9 覆写 `_build_cursor()` 方法，使用最新 tweet ID 作为水印
- [x] 2.10 实现 `test_connection()` 方法，验证 API Key 和连通性

## 3. 注册集成

- [x] 3.1 在 `ainews/fetcher/registry.py` 中 import TwitterFetcher 并注册 `twitter` 数据源

## 4. 配置文件

- [x] 4.1 更新 `~/.ainews/config.yaml`，新增 `sources.twitter` 配置段（含默认 AI KOL 账户列表和搜索模板）

## 5. 文档更新

- [x] 5.1 更新 `docs/03-data-sources.md`，将 P3 X/Twitter 章节更新为已实现状态，补充实际 API 用法和配置说明

## 6. 测试

- [x] 6.1 编写 `tests/test_fetcher_twitter.py`，覆盖配置解析、推文标准化、过滤逻辑、水印构建等核心逻辑（mock API 响应）

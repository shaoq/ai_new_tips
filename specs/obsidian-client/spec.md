## ADDED Requirements

### Requirement: Obsidian REST API 客户端初始化
系统 SHALL 实现 ObsidianClient 类，使用 httpx 连接 Obsidian Local REST API。连接配置从 `~/.ainews/config.yaml` 的 `obsidian` 配置组读取：vault_path、api_key、port（默认 27124）。客户端 SHALL 配置 Bearer Token 认证、`verify=False`（自签名证书）、10 秒连接超时。

#### Scenario: 初始化客户端
- **WHEN** 系统创建 ObsidianClient 实例
- **THEN** 客户端配置 base_url 为 `https://127.0.0.1:{port}`，设置 `Authorization: Bearer {api_key}` 头，禁用 SSL 验证

### Requirement: 连接健康检查
系统 SHALL 提供 `health_check()` 方法，调用 `GET /` 验证 Obsidian REST API 是否可用。返回布尔值表示连接状态。

#### Scenario: Obsidian 运行中
- **WHEN** 调用 `health_check()` 且 Obsidian 正在运行
- **THEN** 返回 `True`，日志记录连接成功

#### Scenario: Obsidian 未运行
- **WHEN** 调用 `health_check()` 且 Obsidian 未运行（连接被拒绝）
- **THEN** 返回 `False`，日志记录连接失败及原因

### Requirement: 自动降级到文件系统
当 REST API 健康检查失败时，系统 SHALL 自动切换为文件系统写入模式，直接操作 `obsidian.vault_path` 目录。降级 SHALL 记录 WARNING 级别日志。

#### Scenario: REST API 不可用时降级
- **WHEN** `health_check()` 返回 `False` 后执行同步操作
- **THEN** 系统切换为文件系统模式，所有写入操作直接操作 vault_path 目录

#### Scenario: REST API 恢复后不自动升级
- **WHEN** 当前处于文件系统降级模式
- **THEN** 本次运行期间不会自动切回 REST API 模式（下次运行重新检测）

### Requirement: REST API 操作封装
系统 SHALL 封装以下 REST API 操作：
- `put_vault_file(path, content)` -> `PUT /vault/{path}`，创建或覆盖文件
- `patch_periodic_daily(heading, content)` -> `PATCH /periodic/daily/`，追加到当日笔记指定 heading
- `patch_frontmatter(path, fields)` -> `PATCH /vault/{path}` + `Target-Type: frontmatter`，更新 frontmatter 字段
- `search_simple(query)` -> `POST /search/simple/`，搜索 Vault 内容
- `get_vault_file(path)` -> `GET /vault/{path}`，读取文件内容

#### Scenario: 创建文章文件
- **WHEN** 调用 `put_vault_file("AI-News/Industry/2026-04-13-openai-gpt6.md", content)`
- **THEN** 发送 `PUT https://127.0.0.1:27124/vault/AI-News/Industry/2026-04-13-openai-gpt6.md`，携带 content 作为请求体

#### Scenario: 追加每日笔记
- **WHEN** 调用 `patch_periodic_daily("08:00 更新 (10篇)", "- [[article|title]] ...")`
- **THEN** 发送 `PATCH https://127.0.0.1:27124/periodic/daily/`，Headers 包含 `Target-Type: heading`、`Operation: append`

### Requirement: 请求重试
系统 SHALL 对连接错误和 5xx 响应自动重试，最多 3 次，指数退避间隔（1s、2s、4s）。4xx 错误不重试。

#### Scenario: 连接超时后重试成功
- **WHEN** 首次请求因连接超时失败，第二次重试成功
- **THEN** 操作正常完成，日志记录重试事件

#### Scenario: 重试耗尽后降级
- **WHEN** 3 次重试全部失败
- **THEN** 切换为文件系统降级模式，日志记录重试耗尽

### Requirement: 文件系统写入操作
文件系统降级模式 SHALL 提供与 REST API 等价的写入能力：
- 创建目录（如不存在）
- 写入 `.md` 文件
- 追加内容到已有文件
- 读取文件内容

#### Scenario: 文件系统模式创建文章
- **WHEN** 处于文件系统降级模式且创建文章文件
- **THEN** 系统创建 `{vault_path}/AI-News/{category}/` 目录（如不存在），写入 `{date-slug}.md` 文件

#### Scenario: 文件系统模式追加每日笔记
- **WHEN** 处于文件系统降级模式且追加每日笔记
- **THEN** 系统追加内容到 `{vault_path}/AI-News/Daily/{YYYY-MM-DD}.md`，文件不存在时创建并写入头部

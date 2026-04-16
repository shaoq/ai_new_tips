## 1. 存储文档更新 (`docs/08-data-storage.md`)

- [x] 1.1 articles 表 CREATE TABLE 语句中补充 `title_zh TEXT DEFAULT ""` 字段（位于 title 之后）

## 2. CLI 文档更新 (`docs/09-cli-design.md`)

- [x] 2.1 命令总览中补充 `ainews dedup` 子命令
- [x] 2.2 命令总览中补充 `ainews trend` 子命令
- [x] 2.3 命令总览中补充 `ainews doctor` 子命令
- [x] 2.4 补充 `pipeline/runner.py` 的 RunOptions 模式和 Step 执行流程说明
- [x] 2.5 补充 Step 级进度反馈描述（各 Step 的 OK/FAIL 输出格式）

## 3. 验证

- [x] 3.1 对照 `ainews/cli/` 目录验证所有子命令已列出
- [x] 3.2 对照 `ainews/storage/models.py` 验证 articles 表字段完整

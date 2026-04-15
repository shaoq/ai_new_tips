## 1. 数据模型

- [x] 1.1 Article 模型新增 `title_zh: str = Field(default="")` 字段 (storage/models.py)
- [x] 1.2 创建 DB migration 为 articles 表添加 title_zh 列（VARCHAR DEFAULT ''）

## 2. LLM Prompt 与 Processor

- [x] 2.1 MERGED_PROCESS_PROMPT 增加 `title_zh` 输出要求（简洁中文标题翻译）(llm/prompts.py)
- [x] 2.2 ProcessResult dataclass 增加 `title_zh` 字段 (processor/processor.py)
- [x] 2.3 ArticleProcessor._apply_result() 解析并写入 `article.title_zh` (processor/processor.py)

## 3. Publisher 层显示切换

- [x] 3.1 钉钉 formatter 优先使用 title_zh，回退到 title (publisher/formatter.py)
- [x] 3.2 Obsidian frontmatter 同时包含 title 和 title_zh (publisher/obsidian_templates.py)
- [x] 3.3 Obsidian daily note wiki-link 显示文本使用 title_zh (publisher/obsidian_templates.py)
- [x] 3.4 CLI run.py push 步骤使用 title_zh 构建推送字典 (cli/run.py)

## 4. 历史数据回填

- [x] 4.1 ArticleProcessor 新增 `backfill_title_zh()` 方法，查询 processed=True 且 title_zh="" 的文章并补翻译
- [x] 4.2 CLI process 命令增加 `--backfill-title-zh` 选项和 `--limit` 参数

## 5. 测试与文档

- [x] 5.1 单元测试: LLM prompt 输出包含 title_zh 字段
- [x] 5.2 单元测试: Processor 正确解析并写入 title_zh
- [x] 5.3 单元测试: Publisher 层 title_zh 回退逻辑
- [x] 5.4 更新 docs/05-llm-processing.md 文档

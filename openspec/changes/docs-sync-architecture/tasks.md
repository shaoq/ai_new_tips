## 1. 模块划分重写

- [x] 1.1 用 `find ainews/ -name "*.py"` 生成完整的实际文件列表
- [x] 1.2 重写 `docs/02-architecture.md` 的"模块划分"部分，准确列出每个子目录的文件及一句职责说明
- [x] 1.3 删除所有不存在的文件引用（processor/classifier.py, processor/summarizer.py, processor/scorer.py, processor/tagger.py, config/schema.py, storage/migrations.py, utils/url.py, utils/text.py, utils/crypto.py）
- [x] 1.4 补充遗漏的目录和文件（trend/ 8个文件, pipeline/runner.py, publisher/ 9个文件拆分, fetcher/runner.py, fetcher/github_releases.py, config/loader.py, storage/crud.py）

## 2. 数据流和流水线更新

- [x] 2.1 更新"数据流"图，反映 `pipeline/runner.py` 的 Step 执行模式（fetch → process → dedup → trend → sync → push）
- [x] 2.2 在 Step 2 (process) 中补充 title_zh 生成步骤
- [x] 2.3 在各 Step 中补充 pipeline-progress-feedback 的进度输出描述
- [x] 2.4 更新"完整流水线"部分，确保与实际代码一致

## 3. 验证

- [x] 3.1 对照实际 `ainews/` 目录结构验证文档中每个文件路径都存在
- [x] 3.2 验证无虚构文件路径

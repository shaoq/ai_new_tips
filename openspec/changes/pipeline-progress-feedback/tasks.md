## 1. PipelineRunner 步骤进行中提示

- [x] 1.1 在 `pipeline/runner.py` 的 `run()` 方法中，步骤执行前添加 `console.print` 输出 `▸ StepName...`
- [x] 1.2 验证 `ainews run` 输出：每个步骤开始时可见进行中提示，完成后可见结果行

## 2. Fetch 逐源采集进度

- [x] 2.1 在 `fetcher/runner.py` 中引入 `rich.console.Console`（模块级，注明依赖来源）
- [x] 2.2 在 `run_fetch()` 每个源采集成功后添加 `console.print` 输出源名、文章数、耗时
- [x] 2.3 在 `run_fetch()` 每个源采集失败后添加 `console.print` 输出失败信息
- [x] 2.4 验证 `ainews fetch run` 单独调用时逐源进度可见

## 3. Process 批量处理进度

- [x] 3.1 在 `processor/processor.py` 中引入 `rich.console.Console`（模块级，注明依赖来源）
- [x] 3.2 在 `process_unprocessed()` 循环中添加每 5 篇及最后一篇的进度打印
- [x] 3.3 在 `process_all_force()` 循环中添加相同逻辑的进度打印
- [x] 3.4 验证少于 5 篇时仅在完成时打印一行，0 篇时不打印进度

## 4. 集成验证

- [x] 4.1 运行 `ainews run` 确认完整流水线输出流畅、进度行与 summary 表格视觉层级清晰
- [x] 4.2 同步更新 `docs/03-data-sources.md`（fetch 进度输出）和 `docs/05-llm-processing.md`（process 进度输出）

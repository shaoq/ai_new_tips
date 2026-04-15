## 1. Bug 修复

- [x] 1.1 在 `ainews/cli/run.py` 的 `_step_push()` 中，调用 `build_feedcard()` 前将 `list[Article]` 转为 `list[dict]`

## 2. 验证

- [x] 2.1 运行 `ainews run` 验证 Push DingTalk 步骤不再报错

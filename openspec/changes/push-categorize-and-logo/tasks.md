## 1. Source Mapping 模块

- [x] 1.1 创建 `ainews/publisher/source_map.py`，实现 `get_source_type(source: str) -> str` 和 `get_favicon_url(source: str) -> str` 函数
- [x] 1.2 定义 source→source_type 映射表（article/paper/repo）和 source→favicon URL 映射表
- [x] 1.3 为未知 source 提供 fallback：source_type 默认 `"article"`，favicon 使用通用兜底图片

## 2. Formatter 层改造

- [x] 2.1 修改 `build_feedcard`：为每条卡片标题添加 `[文章]`/`[论文]`/`[仓库]` 前缀
- [x] 2.2 修改 `build_feedcard`：填充 `picURL` 字段（从 article dict 的 `pic_url` 取值）
- [x] 2.3 修改 `build_feedcard`：按 source_type 排序（article → paper → repo），同类型按 trend_score 降序
- [x] 2.4 修改 `build_markdown_noon`：在每条标题后添加来源类型标签（如 `[论文]`）
- [x] 2.5 修改 `build_markdown_weekly`：Top 5 热点文章标题后添加来源类型标签

## 3. Push CLI 层改造

- [x] 3.1 修改 `_article_to_dict`：调用 `source_map` 补充 `source_type` 和 `pic_url` 字段
- [x] 3.2 验证所有推送模式（晨报/午间/晚报/热点/周报/单篇）均使用更新后的 `_article_to_dict`

## 4. 测试

- [x] 4.1 为 `source_map.py` 编写单元测试（映射正确性、fallback 行为）
- [x] 4.2 为 `build_feedcard` 编写测试（标题前缀、picURL 填充、排序逻辑）
- [x] 4.3 为 markdown 格式编写测试（来源类型标签）
- [ ] 4.4 手动端到端验证：发送测试消息到钉钉确认图片和前缀显示正常

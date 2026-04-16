## 1. RSS 源更新

- [x] 1.1 从 `DEFAULT_RSS_FEEDS` 中移除 6 个失效源：marktechpost、anthropic-news、anthropic-research、developers-digest、codecentric、ccino-org
- [x] 1.2 向 `DEFAULT_RSS_FEEDS` 中新增 3 个源：techcrunch-ai、aws-ml-blog、simonwillison

## 2. 中文源更新

- [x] 2.1 将 `DEFAULT_CHINESE_SOURCES` 中的 aibase 替换为 36kr（name: "36kr", url: "https://www.36kr.com/feed", method: "rss"）
- [x] 2.2 向 `DEFAULT_CHINESE_SOURCES` 中新增 ifanr（name: "ifanr", url: "https://www.ifanr.com/feed", method: "rss"）
- [x] 2.3 从 `_SOURCE_SELECTORS` 中移除 aibase 选择器条目

## 3. 验证

- [x] 3.1 运行测试确保无回归
- [x] 3.2 验证所有新增 RSS 源可正常拉取（手动 curl 确认）

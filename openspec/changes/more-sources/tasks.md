## 1. RSS Feed 扩展

- [x] 1.1 在 `ainews/fetcher/rss.py` 的 `DEFAULT_RSS_FEEDS` 中新增 Anthropic 官方源：anthropic-news、anthropic-research
- [x] 1.2 在 `DEFAULT_RSS_FEEDS` 中新增社区源：reddit-claudeai、reddit-anthropicai、devto-claude
- [x] 1.3 在 `DEFAULT_RSS_FEEDS` 中新增 Newsletter/博客源：developers-digest、pragmatic-engineer、ai-maker、the-ai-corner、alexop-dev、codecentric、changelog
- [x] 1.4 在 `DEFAULT_RSS_FEEDS` 中新增中文源：ccino-org、tony-bai、hellogithub
- [x] 1.5 在 `DEFAULT_RSS_FEEDS` 中新增 GitHub Trending 源：github-trending-python-daily、github-trending-all-weekly
- [x] 1.6 在 `DEFAULT_RSS_FEEDS` 中新增 LibHunt 开源推荐源：libhunt-python、libhunt-selfhosted

## 2. 现有 Fetcher 常量扩展

- [x] 2.1 在 `ainews/fetcher/hackernews.py` 的 `AI_KEYWORDS` 列表中新增关键词：agentic、cursor、windsurf、codex、aider、coding assistant、computer use
- [x] 2.2 在 `ainews/fetcher/arxiv.py` 的 `DEFAULT_CATEGORIES` 列表中新增 cs.CV、stat.ML
- [x] 2.3 在 `ainews/fetcher/reddit.py` 的默认子版列表中新增 artificial、deeplearning、ClaudeAI
- [x] 2.4 在 `ainews/fetcher/chinese.py` 中新增 `DEFAULT_CHINESE_SOURCES` 常量（qbitai、jiqizhixin、aibase 的 RSS URL），并修改 `__init__` 使其在无配置时使用默认源
- [x] 2.5 在 `ainews/fetcher/twitter.py` 的 `DEFAULT_SEARCH_QUERY` 中增加 `"claude code"` 搜索词

## 3. GitHub Releases Fetcher（新增）

- [x] 3.1 在 `ainews/config/settings.py` 中新增 `GitHubReleasesConfig` 配置类（repos 列表、enabled、token）
- [x] 3.2 创建 `ainews/fetcher/github_releases.py`，继承 BaseFetcher，实现 GitHub Releases API 调用
- [x] 3.3 默认监控仓库（12 个）：
  - 工具类：anthropics/claude-code、anthropics/anthropic-sdk-python、anthropics/courses
  - 资源/指南类：e2b-dev/awesome-ai-agents、taishi-i/awesome-ChatGPT-repositories、lukasmasuch/best-of-ml-python、FlorianBruniaux/claude-code-ultimate-guide
  - GitHub 仓库推荐类：GitHubDaily/GitHubDaily、OpenGithubs/weekly、OpenGithubs/github-weekly-rank、GrowingGit/GitHub-Chinese-Top-Charts、EvanLi/Github-Ranking
- [x] 3.4 处理无 release 的仓库（记录 warning 并跳过，不报错）
- [x] 3.5 在 `ainews/fetcher/registry.py` 中注册 `github-releases` fetcher
- [x] 3.6 在 `ainews/config/settings.py` 的 `SourcesConfig` 中添加 `github_releases` 字段

## 4. 文档更新

- [x] 4.1 更新 `docs/03-data-sources.md`，补充所有新增源的说明（RSS feeds、GitHub Trending、LibHunt、GitHub Releases、Chinese 默认源、Twitter 优化）

## 5. 测试

- [x] 5.1 为 `github_releases.py` 编写单元测试（mock GitHub API 响应，覆盖工具类、资源类、推荐类仓库，以及无 release 仓库的容错）
- [x] 5.2 为扩展后的 `DEFAULT_RSS_FEEDS`（含 GitHub Trending、LibHunt、HelloGitHub）、`AI_KEYWORDS`、`DEFAULT_CATEGORIES` 等常量编写验证测试
- [x] 5.3 为 `DEFAULT_CHINESE_SOURCES` 编写测试（验证默认源加载和覆盖逻辑）

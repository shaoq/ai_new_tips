## 1. URL 标准化与去重模块

- [x] 1.1 实现 `ainews/trend/url_normalizer.py`：`normalize_url()` 函数，解析 URL、移除 www、去除 trailing slash、移除 tracking 参数（utm_* 等），返回标准化字符串
- [x] 1.2 实现 URL hash 匹配逻辑：对标准化 URL 计算 SHA256，通过 articles.url_hash 进行快速查重
- [x] 1.3 实现 `ainews/trend/dedup.py`：`dedup_articles()` 函数，扫描未去重文章，通过标题相似度 > 0.9 检测重复，标记 status='duplicate'

## 2. 标题语义聚类

- [x] 2.1 实现 `ainews/trend/title_cluster.py`：`title_similarity()` 函数（SequenceMatcher），接受两个标题字符串返回 0-1 相似度
- [x] 2.2 实现 `cluster_titles()` 函数：对指定时间范围内的文章执行 N^2 相似度比较（相似度 > 0.8 归入同一聚类），返回聚类列表
- [x] 2.3 将聚类结果写入 clusters 表：创建/更新 cluster 记录，包含 topic、article_ids、source_count

## 3. 跨源关联引擎

- [x] 3.1 实现 `ainews/trend/correlator.py`：`CrossSourceCorrelator` 类，整合 URL 匹配和标题聚类结果
- [x] 3.2 实现 `correlate()` 方法：对指定时间范围内的文章执行关联，输出关联组（每组包含来自不同源的文章 ID 列表）
- [x] 3.3 更新关联文章的 platforms 字段：根据关联结果，为每篇文章更新 platforms JSON 数组

## 4. 单源热度算法

- [x] 4.1 实现 `ainews/trend/hotness.py`：`calculate_hn_score()` 函数（HN 官方排名算法，gravity=1.8）
- [x] 4.2 实现 `calculate_reddit_hot()` 函数（Reddit Hot 算法，对数缩放 + 时间衰减）
- [x] 4.3 实现 `calculate_hf_hotness()` 函数（基于 upvotes 的分段阈值）
- [x] 4.4 实现 `calculate_github_velocity()` 函数（基于 stars 增长速度）
- [x] 4.5 实现各平台归一化函数：将原始分数映射到 [0, 1]，使用 sigmoid-like 映射
- [x] 4.6 实现 `get_platform_hotness()` 统一入口：根据 source 类型分发到对应算法

## 5. 综合趋势评分

- [x] 5.1 实现 `ainews/trend/scorer.py`：`calculate_trend_score()` 函数，综合 platform_hotness * 0.35 + cross_platform_bonus * 0.35 + velocity * 0.20，乘以 novelty_bonus，结果 0-10
- [x] 5.2 实现 `calculate_velocity()` 函数：从 source_metrics 表计算增长速度（分数/小时）
- [x] 5.3 实现 `determine_novelty_bonus()` 函数：检查关联文章是否涉及新实体，有则返回 1.2，否则 1.0
- [x] 5.4 实现 `update_trend_scores()` 函数：对指定范围内的文章批量计算并更新 trend_score、is_trending（>= 6 为 TRUE）

## 6. 实体发现引擎

- [x] 6.1 实现 `ainews/trend/entity_discovery.py`：`discover_entities()` 函数，从已处理文章的 entities JSON 字段提取实体列表
- [x] 6.2 实现 `match_known_entities()` 函数：将提取的实体与 entities 表比对，区分已知/新实体
- [x] 6.3 实现新实体入库：创建 entities 记录（is_new=TRUE），创建 article_entities 关联
- [x] 6.4 实现已知实体更新：mention_count 递增，更新 metadata

## 7. 自动发现机制

- [x] 7.1 实现 `ainews/trend/auto_discover.py`：`discover_emerging_researchers()` 函数，查询近期 ArXiv 文章作者，通过 Semantic Scholar API 检查引用加速度，标记 emerging_researcher
- [x] 7.2 实现 `discover_new_projects()` 函数：筛选 Show HN 帖子（points > 50）+ GitHub 新仓库（一周 500+ stars），交叉验证
- [x] 7.3 实现 `discover_new_companies()` 函数：从 LLM 提取的 company 实体中，检测首次出现的公司，标记 new_company

## 8. CLI 命令：trend

- [x] 8.1 实现 `ainews/cli/trend.py`：`ainews trend` 命令，执行完整趋势分析流水线（关联 -> 评分 -> 实体发现）
- [x] 8.2 支持 `--days N` 参数：指定分析时间范围（默认 1 天）
- [x] 8.3 支持 `--dry-run` 参数：仅输出分析结果，不写入数据库
- [x] 8.4 输出分析摘要：关联组数、热点文章数、新实体数

## 9. CLI 命令：dedup

- [x] 9.1 实现 `ainews/cli/dedup.py`：`ainews dedup` 命令，执行标题相似度去重
- [x] 9.2 支持 `--threshold` 参数：自定义相似度阈值（默认 0.9）
- [x] 9.3 输出去重结果：检测到的重复对数、标记的文章数

## 10. CLI 命令：entities

- [x] 10.1 实现 `ainews/cli/entities.py`：`ainews entities` 命令，管理实体库
- [x] 10.2 实现默认行为：列出最近发现的实体（`--days 7 --limit 20`）
- [x] 10.3 支持 `--type` 过滤：按 person/company/project/technology 筛选
- [x] 10.4 支持 `--new-only` 参数：仅显示 is_new=TRUE 的实体

## 11. CLI 命令：stats

- [x] 11.1 实现 `ainews/cli/stats.py`：`ainews stats` 命令组，注册所有子命令
- [x] 11.2 实现 `stats today`：今日概览（文章数、热点数、top 3 热点标题、新实体数），Rich 表格输出
- [x] 11.3 实现 `stats weekly`：本周概览（同 today 但时间范围 7 天，含趋势变化）
- [x] 11.4 实现 `stats trending`：热点排行（trend_score DESC，默认 top 20），支持 `--days` 和 `--limit` 参数
- [x] 11.5 实现 `stats by-source`：来源分布（各源文章数、热点数占比），Rich 表格输出
- [x] 11.6 实现 `stats by-category`：分类分布（industry/research/tools/safety/policy 各类文章数），Rich 表格输出
- [x] 11.7 实现 `stats new-entities`：新发现实体列表，支持 `--days` 和 `--type` 参数
- [x] 11.8 实现 `stats top-people`：人物活跃度排行（mention_count DESC），支持 `--days` 和 `--limit` 参数

## 12. 测试

- [x] 12.1 测试 URL 标准化：各种 URL 格式的归一化结果（`tests/trend/test_url_normalizer.py`）
- [x] 12.2 测试标题相似度：相同/相似/不同标题的相似度计算（`tests/trend/test_title_cluster.py`）
- [x] 12.3 测试单源热度算法：HN/Reddit/HF/GitHub 各算法的评分计算（`tests/trend/test_hotness.py`）
- [x] 12.4 测试综合趋势评分：不同参数组合的评分结果和边界值（`tests/trend/test_scorer.py`）
- [x] 12.5 测试实体发现：新实体检测和已知实体更新（`tests/trend/test_entity_discovery.py`）
- [x] 12.6 测试 CLI 命令：trend/dedup/entities/stats 各子命令的输出（`tests/cli/test_trend_cli.py`、`tests/cli/test_stats_cli.py`）
- [x] 12.7 确认测试覆盖率 >= 80%

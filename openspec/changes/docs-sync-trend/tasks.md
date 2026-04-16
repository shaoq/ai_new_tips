## 1. 架构图更新

- [x] 1.1 更新 `docs/04-hot-topic-detection.md` 三层热点检测架构图，Layer 内部模块名替换为实际 `trend/` 目录文件名

## 2. 模块说明替换伪代码

- [x] 2.1 将 `normalize_url()` 伪代码替换为 `trend/url_normalizer.py` 模块说明
- [x] 2.2 将 `title_similarity()` 伪代码替换为 `trend/title_cluster.py` 模块说明
- [x] 2.3 将 `calculate_trend_score()` 伪代码替换为 `trend/scorer.py` + `trend/hotness.py` 模块说明
- [x] 2.4 将 `detect_new_entities()` 伪代码替换为 `trend/entity_discovery.py` + `trend/auto_discover.py` 模块说明
- [x] 2.5 补充 `trend/correlator.py` 跨源关联模块说明
- [x] 2.6 补充 `trend/dedup.py` 内容指纹去重模块说明

## 3. 评分算法和去重更新

- [x] 3.1 更新综合评分算法描述，与 `trend/scorer.py` 实际实现一致
- [x] 3.2 确认评分含义表（0-4/4-6/6-8/8-10）与代码一致

## 4. 验证

- [x] 4.1 对照 `ainews/trend/` 目录验证文档中每个模块引用都存在

# CLI 命令设计

## 命令总览

```
ainews
├── config          配置管理
│   ├── init        交互式初始化
│   ├── show        查看当前配置
│   └── set <key> <value>  修改配置项
├── sources         订阅源管理
│   ├── list        查看所有源及状态
│   ├── add         添加订阅源
│   ├── remove      移除订阅源
│   ├── enable      启用源
│   ├── disable     禁用源
│   └── test        测试源可用性
├── fetch           拉取最新内容
├── process         智能处理 (分类+摘要+评分)
├── dedup           去重检查
├── trend           跨源关联+热点评分
├── entities        实体提取
├── sync            同步输出
│   └── obsidian    同步到 Obsidian
├── push            推送通知
│   └── dingtalk    推送到钉钉
├── run             完整流水线 (最常用)
├── stats           统计查询
│   ├── today       今日概览
│   ├── weekly      本周概览
│   ├── monthly     本月概览
│   ├── trending    热点排行
│   ├── by-source   来源分布
│   ├── by-category 分类分布
│   ├── new-entities 新发现实体
│   └── top-people  人物活跃度
├── cron            定时任务管理
│   ├── install     安装定时任务
│   ├── uninstall   卸载定时任务
│   ├── list        查看定时配置
│   ├── pause       暂停定时任务
│   ├── resume      恢复定时任务
│   └── trigger     立即触发一次
├── db              数据库管理
│   ├── status      数据库状态
│   ├── cleanup     清理旧数据
│   └── export      导出数据
├── show            查看文章详情
├── search          搜索文章
├── doctor          环境检查
└── --version       版本信息
```

## 核心命令详解

### ainews config init

交互式初始化，引导用户完成首次配置。

```bash
$ ainews config init

🚀 AI News Tips 初始化

? LLM Base URL: [https://api.anthropic.com]
? API Key: [sk-ant-xxx]
? Model: [claude-haiku-4-5-20251001]
? Obsidian Vault Path: [/Users/jie.hua/MyVault]
? Obsidian REST API Key: [xxx]
? Obsidian REST API Port: [27124]
? DingTalk Webhook URL: [https://oapi.dingtalk.com/robot/send?access_token=xxx]
? DingTalk Secret: [SEC-xxx]

✅ 配置已保存至 ~/.ainews/config.yaml
```

### ainews run

完整流水线，最常用的命令。

```bash
ainews run                          # 标准执行: fetch→process→dedup→trend→sync→push
ainews run --backfill 7d            # 首次运行，回溯 7 天
ainews run --source hackernews      # 只拉取指定源
ainews run --no-push                # 不推送钉钉
ainews run --skip-push              # 同上
ainews run --trending-only-push     # 只推送热点 (trend_score ≥ 8)
ainews run --skip-sync              # 不同步 Obsidian
ainews run -v / --verbose           # 详细日志
ainews run --dry-run                # 只看会做什么，不实际执行
```

执行流程:

```
ainews run
  │
  ├── Step 1: fetch
  │     ├─ 读取 fetch_log 获取每个源的上次拉取时间
  │     ├─ 并发拉取所有已启用源
  │     ├─ URL 去重入库
  │     └─ 更新 fetch_log cursor
  │
  ├── Step 2: process
  │     ├─ 筛选未处理文章
  │     ├─ 批量调用 LLM: 分类+摘要+评分+实体+标签
  │     └─ 标记 processed = true
  │
  ├── Step 3: dedup
  │     └─ 内容指纹去重 (标题相似度 > 0.9)
  │
  ├── Step 4: trend
  │     ├─ 跨源关联: URL 匹配 + 标题聚类
  │     ├─ 计算趋势分
  │     └─ 检测新实体
  │
  ├── Step 5: sync obsidian
  │     ├─ 写入文章文件
  │     ├─ 追加每日笔记
  │     └─ 同步实体页面
  │
  └── Step 6: push dingtalk
        ├─ 根据策略选择格式
        ├─ 发送 Webhook
        └─ 标记已推送
```

### ainews fetch

只拉取数据，不处理。

```bash
ainews fetch                        # 拉取所有已启用源
ainews fetch --source hackernews    # 只拉 HackerNews
ainews fetch --source hackernews,reddit
ainews fetch --backfill 7d          # 首次回溯 7 天
ainews fetch --force                # 强制重新拉取 (忽略 cursor)
ainews fetch --dry-run              # 预览模式
```

### ainews sources

管理订阅源。

```bash
ainews sources list                 # 查看所有源及状态
ainews sources enable hackernews    # 启用
ainews sources disable reddit       # 禁用

# 添加 RSS 源
ainews sources add rss --name "OpenAI Blog" --url "https://openai.com/blog/rss.xml"

# 添加 Reddit
ainews sources add reddit --subreddit MachineLearning

# 添加 ArXiv
ainews sources add arxiv --categories cs.AI,cs.LG,cs.CL

# 添加 HuggingFace Papers
ainews sources add hf-papers

# 添加 GitHub Trending
ainews sources add github-trending --topic ai

# 测试源
ainews sources test hackernews
```

### ainews sync obsidian

同步到 Obsidian。

```bash
ainews sync obsidian                # 同步未写入的文章
ainews sync obsidian --test         # 测试连接
ainews sync obsidian --init-dashboards  # 初始化仪表盘模板
ainews sync obsidian --sync-entities    # 同步实体页面
ainews sync obsidian --rebuild-dashboards  # 重建仪表盘
```

### ainews push dingtalk

推送到钉钉。

```bash
ainews push dingtalk                # 推送未推送的文章
ainews push dingtalk --format feedcard --limit 10
ainews push dingtalk --format markdown
ainews push dingtalk --trending-only  # 只推热点
ainews push dingtalk --article "2026-04-13-openai-gpt6"  # 推送单篇
ainews push dingtalk --weekly       # 推送周报
ainews push dingtalk --test         # 发送测试消息
```

### ainews stats

统计查询。

```bash
ainews stats today                  # 今日概览
ainews stats weekly                 # 本周概览
ainews stats trending               # 热点排行
ainews stats by-source              # 来源分布
ainews stats by-category            # 分类分布
ainews stats new-entities --days 7  # 新发现实体
ainews stats top-people --days 30 --limit 20
```

### ainews search

搜索文章。

```bash
ainews search "GPT-6"               # 关键词搜索
ainews search --tag llm --tag openai # 按标签搜索
ainews search --category research --days 7  # 按分类+时间
```

### ainews cron

定时任务管理。

```bash
ainews cron install                 # 安装定时任务
ainews cron list                    # 查看当前配置
ainews cron uninstall               # 卸载全部
ainews cron uninstall --name noon   # 只卸载午间那次
ainews cron pause                   # 暂停
ainews cron resume                  # 恢复
```

## 日常使用速查

```
┌─────────────────────┬──────────────────────────────────────┐
│ 场景                 │ 命令                                 │
├─────────────────────┼──────────────────────────────────────┤
│ 首次使用             │ ainews config init                   │
│                     │ ainews run --backfill 7d             │
├─────────────────────┼──────────────────────────────────────┤
│ 日常 (99%场景)       │ ainews run                           │
│ 看统计               │ ainews stats today                   │
├─────────────────────┼──────────────────────────────────────┤
│ 手动多跑一次         │ ainews run        (增量,不重复)      │
├─────────────────────┼──────────────────────────────────────┤
│ 加一个 RSS 源        │ ainews sources add rss --name X ...  │
├─────────────────────┼──────────────────────────────────────┤
│ 搜文章               │ ainews search "关键词"               │
├─────────────────────┼──────────────────────────────────────┤
│ 装定时任务           │ ainews cron install                  │
│ 停定时任务           │ ainews cron uninstall                │
│ 临时暂停             │ ainews cron pause                    │
├─────────────────────┼──────────────────────────────────────┤
│ 推送周报             │ ainews push dingtalk --weekly         │
│ 测试钉钉             │ ainews push dingtalk --test           │
├─────────────────────┼──────────────────────────────────────┤
│ 检查环境             │ ainews doctor                        │
└─────────────────────┴──────────────────────────────────────┘
```

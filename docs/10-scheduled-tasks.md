# 定时任务与运行策略

## 定时任务清单

```
┌─────────────────────────────────────────────────────────────┐
│  时间          │ 命令                              │ 说明     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  每天 08:00                                                 │
│  ainews run                                                  │
│  → fetch + process + trend + sync obsidian + push dingtalk   │
│  → 推送晨报 (feedCard, Top 10)                               │
│                                                              │
│  每天 12:30                                                 │
│  ainews run --trending-only-push                             │
│  → fetch + process + trend + sync obsidian                   │
│  → 只推送热点 (trend_score ≥ 8 的 actionCard)                │
│  → 无热点则不推送 (不打扰)                                    │
│                                                              │
│  每天 20:00                                                 │
│  ainews run                                                  │
│  → fetch + process + trend + sync obsidian + push dingtalk   │
│  → 推送晚报 (feedCard, 全部增量)                              │
│                                                              │
│  每周日 20:30 (在晚报之后)                                    │
│  ainews push dingtalk --weekly                               │
│  → 推送本周周报 (markdown 格式)                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 各时间点执行流

### 08:00 晨跑

```
ainews run
┌──────────────────────────────────────────────┐
│  1. fetch     拉取全部源 (处理夜间增量)        │
│  2. process   分类 + 摘要 + 评分              │
│  3. dedup     去重                            │
│  4. trend     跨源关联 + 热点评分             │
│  5. sync      写入 Obsidian                  │
│     ├─ 新文章 → 分类文件夹                   │
│     ├─ 追加 → Daily/2026-04-14.md            │
│     │       ## 08:00 更新 (N篇)              │
│     └─ 同步新实体页面                        │
│  6. push      钉钉推送晨报                    │
│     └─ feedCard 格式, Top 10                 │
└──────────────────────────────────────────────┘
```

### 12:30 午跑

```
ainews run --trending-only-push
┌──────────────────────────────────────────────┐
│  1. fetch     拉取上午增量                    │
│  2. process   处理新文章                      │
│  3. dedup + trend                            │
│  4. sync      写入 Obsidian                  │
│     └─ 追加 → Daily/2026-04-14.md            │
│            ## 12:30 更新 (N篇)               │
│  5. push      仅推送热点                      │
│     ├─ trend_score ≥ 8 → actionCard          │
│     ├─ 每天最多 3 条即时推送                  │
│     └─ 无热点则不推送 (静默)                  │
└──────────────────────────────────────────────┘
```

### 20:00 晚跑

```
ainews run
┌──────────────────────────────────────────────┐
│  1-4. 同晨跑 (拉取+处理+同步)                 │
│  5. sync      追加 → Daily/2026-04-14.md     │
│               ## 20:00 更新 (N篇)            │
│  6. push      钉钉推送晚报                    │
│     └─ feedCard, 当日全部新文章               │
└──────────────────────────────────────────────┘
```

### 周日 20:30 周报

```
ainews push dingtalk --weekly
┌──────────────────────────────────────────────┐
│  → 汇总本周统计                              │
│  → 推送周报 (markdown 格式)                   │
│  → 含: Top 5热点 / 新人物 / 来源分布         │
└──────────────────────────────────────────────┘
```

## 手动运行

```bash
# 随时手动运行，效果与定时完全一致
# 增量逻辑保证不重复，Daily 笔记追加新段落
ainews run

# 只拉不同步不推
ainews run --skip-sync --skip-push

# 只看拉到了什么
ainews fetch && ainews stats today
```

**多次运行不冲突：**
- URL 去重：同一文章不会重复创建
- Daily 笔记：每次运行追加一个 `## HH:MM 更新` 段落
- 钉钉推送：已推送的文章不会重复推送 (dingtalk_sent 字段)
- Obsidian：已同步的文章不会重复写入

## macOS launchd 实现

### 命令管理

```bash
ainews cron install       # 创建 plist + launchctl load
ainews cron uninstall     # launchctl unload + 删除 plist
ainews cron pause         # launchctl unload (保留 plist)
ainews cron resume        # launchctl load
ainews cron list          # 读取 plist + launchctl status
```

### plist 文件位置

```
~/Library/LaunchAgents/
├── com.ainews.morning.plist     # 08:00
├── com.ainews.noon.plist        # 12:30
├── com.ainews.evening.plist     # 20:00
└── com.ainews.weekly.plist      # 周日 20:30
```

### plist 模板示例 (晨跑)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ainews.morning</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ainews</string>
        <string>run</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ainews-morning.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ainews-morning.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

## 运行控制

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  场景                         │ 操作                 │
│  ────────────────────────────┼───────────────────    │
│  手动跑 ainews run 中途想停   │ Ctrl + C             │
│  不想每天自动跑了             │ ainews cron uninstall│
│  临时暂停几天                 │ ainews cron pause    │
│  暂停后恢复                   │ ainews cron resume   │
│  只取消午间那次               │ ainews cron          │
│                               │  uninstall --name    │
│                               │  noon                │
│  查看当前定时状态             │ ainews cron list     │
│  查看运行日志                 │ cat /tmp/ainews-     │
│                               │  morning.log         │
│                                                      │
│  注意:                                               │
│  Ctrl+C 只能终止终端手动运行的命令                    │
│  定时任务 (launchd) 不在终端运行                      │
│  需要用 ainews cron 命令管理                          │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## 日志

每次运行输出日志到 `~/.ainews/logs/` 和 `/tmp/ainews-*.log`。

```
~/.ainews/logs/
├── 2026-04-14.log          # 按日期归档
└── latest.log              # 最新日志软链接
```

日志格式:

```
[2026-04-14 08:00:01] INFO  ainews run started
[2026-04-14 08:00:02] INFO  fetch: hackernews - 15 new articles
[2026-04-14 08:00:04] INFO  fetch: arxiv - 8 new articles
[2026-04-14 08:00:05] INFO  fetch: reddit - 6 new articles
[2026-04-14 08:00:06] INFO  fetch: rss - 12 new articles
[2026-04-14 08:00:06] INFO  fetch: total 41 new articles
[2026-04-14 08:00:15] INFO  process: 41 articles processed by LLM
[2026-04-14 08:00:16] INFO  dedup: 3 duplicates found
[2026-04-14 08:00:17] INFO  trend: 5 trending articles detected
[2026-04-14 08:00:18] INFO  sync: 38 articles synced to Obsidian
[2026-04-14 08:00:19] INFO  push: dingtalk feedcard sent (10 articles)
[2026-04-14 08:00:19] INFO  ainews run completed in 18s
```

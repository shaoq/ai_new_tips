# AI News Tips - 项目概述

## 项目定位

CLI 工具，自动聚合 AI 相关的文章订阅（HackerNews、ArXiv、Reddit、RSS 等），通过 LLM 智能处理（分类、摘要、评分、实体提取），将结果同步到本地 Obsidian 知识库，并通过钉钉 Webhook 机器人推送增量通知。

## 核心能力

| 能力 | 描述 |
|------|------|
| 多源聚合 | HackerNews / ArXiv / Reddit / RSS / HuggingFace Papers / GitHub Trending / 中文源 |
| 智能处理 | LLM 驱动的自动分类、中文摘要、相关性评分、实体提取 |
| 热点感知 | 跨源关联 + 速度追踪 + 热点评分算法，无需依赖 X/Twitter |
| 自动发现 | 新兴研究员、新 AI 项目/公司、新技术的自动识别与追踪 |
| Obsidian 集成 | 通过 Local REST API 写入，支持分类归档、每日笔记、仪表盘、知识图谱 |
| 钉钉推送 | feedCard 晨晚报、actionCard 即时热点、markdown 周报 |
| 增量机制 | 首次回溯 7 天，后续只处理增量，URL + 内容指纹双重去重 |

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.12+ |
| CLI 框架 | Click 或 Typer |
| 数据库 | SQLite（本地，轻量） |
| RSS 解析 | feedparser |
| HTTP 客户端 | httpx（异步） |
| LLM | 用户自配置（base_url + api_key + model，默认 Anthropic 协议） |
| 定时任务 | macOS launchd |
| 配置管理 | YAML + pydantic-settings |
| 测试 | pytest，80%+ 覆盖率 |

## 月度成本

| 组件 | 成本 |
|------|------|
| HackerNews / ArXiv / Reddit / RSS / HF Papers / GitHub | $0 |
| 中文源 | $0 |
| LLM API（用户自配） | 用户自控 |
| **总计** | **$0 + LLM 费用** |

X/Twitter 作为后续扩展功能（P3 优先级），不在首版范围内。

## 相关文档

- [02-architecture.md](./02-architecture.md) - 系统架构设计
- [03-data-sources.md](./03-data-sources.md) - 数据源详细分析
- [04-hot-topic-detection.md](./04-hot-topic-detection.md) - 热点感知与自动发现
- [05-llm-processing.md](./05-llm-processing.md) - LLM 智能处理
- [06-obsidian-integration.md](./06-obsidian-integration.md) - Obsidian 集成方案
- [07-dingtalk-integration.md](./07-dingtalk-integration.md) - 钉钉推送方案
- [08-data-storage.md](./08-data-storage.md) - 数据存储与增量机制
- [09-cli-design.md](./09-cli-design.md) - CLI 命令设计
- [10-scheduled-tasks.md](./10-scheduled-tasks.md) - 定时任务与运行策略

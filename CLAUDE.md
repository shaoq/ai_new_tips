# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ai_news_tips** (ainews) — Python CLI 工具，自动聚合 AI 相关文章订阅（HackerNews、ArXiv、Reddit、RSS 等），通过 LLM 智能处理（分类、摘要、评分、实体提取），同步到 Obsidian 知识库，并通过钉钉 Webhook 推送通知。

**技术栈**: Python 3.12+, Click/Typer, SQLite (SQLModel), httpx, feedparser, pydantic-settings, pytest

**月度成本**: $0 + 用户自配 LLM API 费用

## Architecture

三层架构 + 持久化：

```
数据采集层 (Fetcher) → 智能处理层 (Processor) → 输出分发层 (Publisher)
                              ↕
                         SQLite 本地存储
```

**数据流**: 多源并发拉取 → URL + 内容指纹去重 → LLM 分类/摘要/评分/实体提取 → 跨源关联热点检测 → Obsidian 归档 + 钉钉推送

**核心流水线** (`ainews run`): fetch → process → dedup → trend → sync obsidian → push dingtalk

## Module Layout

```
ainews/
├── cli/          # CLI 命令入口 (main.py + 各子命令)
├── fetcher/      # 数据采集层 (base.py + 各源实现)
├── processor/    # 智能处理层 (dedup/classifier/summarizer/scorer/entity_extractor/tagger/trend)
├── publisher/    # 输出分发层 (obsidian/dingtalk/formatter)
├── storage/      # 存储层 (database/models/migrations, SQLite + SQLModel)
├── llm/          # LLM 抽象层 (client/prompts/config, Anthropic 协议)
├── scheduler/    # 定时任务 (macOS launchd)
├── config/       # 配置管理 (YAML + pydantic-settings)
├── templates/    # Obsidian 模板 (article/daily/entity/dashboards)
└── utils/        # 工具函数 (url/text/crypto)
```

## OpenSpec Workflow

项目使用 OpenSpec 进行变更管理。当前活跃变更（按实施顺序）：

1. `core-scaffold` — CLI 框架 + 配置管理 + SQLite 存储 + 日志
2. `fetcher-core` — HackerNews / ArXiv / RSS 数据源
3. `fetcher-extended` — Reddit / HuggingFace Papers / GitHub / 中文源
4. `llm-processor` — LLM 客户端 + 文章处理流水线
5. `trend-engine` — 跨源关联 + 热点评分 + 实体发现
6. `obsidian-publisher` — Obsidian REST API 集成
7. `dingtalk-publisher` — 钉钉 Webhook 推送
8. `scheduler-runner` — macOS launchd 定时任务

可用命令: `/opsx:explore`, `/opsx:propose`, `/opsx:apply`, `/opsx:archive`

## Development Commands

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest
pytest tests/test_foo.py::test_bar   # 单个测试

# 运行 CLI
ainews run           # 完整流水线
ainews fetch         # 仅采集
ainews process       # 仅处理
ainews sync          # 同步 Obsidian
ainews push          # 推送钉钉
```

## CRITICAL: Docs Sync Rule

**所有对代码的更新时，务必同步更新 `docs/` 下对应的分析文档。** 代码变更必须反映到文档中，保持文档与代码一致。

文档映射关系：
| 模块 | 对应文档 |
|------|---------|
| 架构/整体 | `docs/02-architecture.md` |
| 数据源/Fetcher | `docs/03-data-sources.md` |
| 热点检测/Trend | `docs/04-hot-topic-detection.md` |
| LLM 处理 | `docs/05-llm-processing.md` |
| Obsidian 集成 | `docs/06-obsidian-integration.md` |
| 钉钉推送 | `docs/07-dingtalk-integration.md` |
| 数据存储 | `docs/08-data-storage.md` |
| CLI 设计 | `docs/09-cli-design.md` |
| 定时任务 | `docs/10-scheduled-tasks.md` |

## Configuration

LLM 通过用户自配置接入（`base_url` + `api_key` + `model`），默认使用 Anthropic 协议。配置存储在本地 YAML 文件中，由 pydantic-settings 管理。

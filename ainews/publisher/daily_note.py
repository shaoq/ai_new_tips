"""每日笔记同步到 Obsidian."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import (
    render_daily_header,
    render_daily_section,
)

logger = logging.getLogger(__name__)


def sync_daily_note(
    client: ObsidianClient,
    articles: list[Any],
    timestamp: datetime | None = None,
) -> bool:
    """将本次同步的文章摘要追加到当日 daily note.

    Args:
        client: ObsidianClient 实例
        articles: 本次同步的文章列表
        timestamp: 时间戳（用于生成 heading）

    Returns:
        是否成功
    """
    if not articles:
        logger.info("没有文章需要追加到每日笔记")
        return True

    if timestamp is None:
        timestamp = datetime.now()

    date_str = timestamp.strftime("%Y-%m-%d")
    section = render_daily_section(articles, timestamp)

    if client.degraded:
        return _sync_daily_note_filesystem(client, date_str, section)
    else:
        return _sync_daily_note_rest(client, date_str, section)


def _sync_daily_note_rest(
    client: ObsidianClient,
    date_str: str,
    section: str,
) -> bool:
    """REST API 模式: 使用 PATCH /periodic/daily/ 追加."""
    # 先检查 daily note 是否存在，不存在则创建头部
    existing = client.get_vault_file(f"AI-News/Daily/{date_str}.md")
    if existing is None:
        header = render_daily_header(date_str)
        client.put_vault_file(f"AI-News/Daily/{date_str}.md", header)

    # 追加更新段落
    heading_text = section.split("\n")[0].strip("#").strip()
    success = client.patch_periodic_daily(heading_text, section)
    if success:
        logger.info("每日笔记追加成功 (REST API): %s", date_str)
    else:
        logger.warning("REST API 追加失败，降级为文件系统模式")
        # 强制使用文件系统写入
        return _sync_daily_note_filesystem_direct(client, date_str, section)
    return success


def _sync_daily_note_filesystem(
    client: ObsidianClient,
    date_str: str,
    section: str,
) -> bool:
    """文件系统降级模式: 直接追加到文件."""
    return _sync_daily_note_filesystem_direct(client, date_str, section)


def _sync_daily_note_filesystem_direct(
    client: ObsidianClient,
    date_str: str,
    section: str,
) -> bool:
    """直接通过文件系统写入（不经过 REST API）."""
    path = f"AI-News/Daily/{date_str}.md"
    full_path = client.vault_path / path

    if full_path.exists():
        # 追加
        try:
            content = full_path.read_text(encoding="utf-8")
            updated = content.rstrip("\n") + "\n\n" + section
            full_path.write_text(updated, encoding="utf-8")
            logger.info("每日笔记追加成功 (文件系统): %s", date_str)
            return True
        except OSError as exc:
            logger.error("追加每日笔记失败: %s", exc)
            return False
    else:
        # 创建新文件: 头部 + 段落
        try:
            header = render_daily_header(date_str)
            content = header + "\n" + section
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            logger.info("每日笔记创建成功 (文件系统): %s", date_str)
            return True
        except OSError as exc:
            logger.error("创建每日笔记失败: %s", exc)
            return False

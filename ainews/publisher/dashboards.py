"""仪表盘初始化: 创建 5 个 Bases 仪表盘模板."""

from __future__ import annotations

import logging
from typing import Any

from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import (
    render_dashboard_articles,
    render_dashboard_home,
    render_dashboard_people_tracker,
    render_dashboard_reading_list,
    render_dashboard_trending,
)

logger = logging.getLogger(__name__)

DASHBOARD_DIR = "AI-News/Dashboards"

# 5 个仪表盘定义 (Bases YAML)
DASHBOARDS: dict[str, Any] = {
    "Home": render_dashboard_home,
    "Trending": render_dashboard_trending,
    "Reading-List": render_dashboard_reading_list,
    "People-Tracker": render_dashboard_people_tracker,
    "Articles": render_dashboard_articles,
}


def init_dashboards(
    client: ObsidianClient,
    rebuild: bool = False,
) -> tuple[int, int]:
    """初始化仪表盘模板文件.

    Args:
        client: ObsidianClient 实例
        rebuild: 是否覆盖已有仪表盘

    Returns:
        (created_count, skipped_count)
    """
    created = 0
    skipped = 0

    for name, renderer in DASHBOARDS.items():
        path = f"{DASHBOARD_DIR}/{name}.base"

        # 检查是否已存在（非重建模式）
        if not rebuild:
            existing = client.get_vault_file(path)
            if existing is not None:
                logger.info("仪表盘已存在，跳过: %s", name)
                skipped += 1
                continue

        # 生成并写入
        content = renderer()
        success = client.put_vault_file(path, content)
        if success:
            created += 1
            logger.info("仪表盘创建成功: %s", name)
        else:
            logger.error("仪表盘创建失败: %s", name)
            skipped += 1

    logger.info(
        "仪表盘初始化完成: %d 创建, %d 跳过", created, skipped
    )
    return created, skipped


def rebuild_dashboards(client: ObsidianClient) -> tuple[int, int]:
    """重建所有仪表盘（覆盖已有文件）."""
    logger.info("开始重建所有仪表盘")
    return init_dashboards(client, rebuild=True)

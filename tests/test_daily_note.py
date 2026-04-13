"""测试每日笔记: 追加段落、头部生成、降级模式."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from ainews.publisher.daily_note import sync_daily_note
from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import render_daily_header


@pytest.fixture
def client(tmp_path: Path) -> ObsidianClient:
    return ObsidianClient(
        api_key="test-key",
        port=27124,
        vault_path=str(tmp_path),
    )


class TestDailyNoteFilesystem:
    """文件系统模式每日笔记测试."""

    def test_create_new_daily_note(
        self, client: ObsidianClient, tmp_path: Path
    ) -> None:
        client._degraded = True
        articles = [
            _make_article("Test Article 1", True, 9.0),
            _make_article("Test Article 2", False, 7.0),
        ]
        ts = datetime(2026, 4, 13, 8, 30)

        result = sync_daily_note(client, articles, ts)
        assert result is True

        file_path = tmp_path / "AI-News" / "Daily" / "2026-04-13.md"
        assert file_path.exists()
        content = file_path.read_text()
        assert "# AI News - 2026-04-13" in content
        assert "## 08:30 更新 (2篇)" in content

    def test_append_to_existing_daily_note(
        self, client: ObsidianClient, tmp_path: Path
    ) -> None:
        client._degraded = True
        # 先创建一个
        daily_path = tmp_path / "AI-News" / "Daily" / "2026-04-13.md"
        daily_path.parent.mkdir(parents=True)
        daily_path.write_text("# AI News - 2026-04-13\n\n## 08:00 更新 (5篇)\n已有内容\n")

        articles = [_make_article("New Article", True, 9.0)]
        ts = datetime(2026, 4, 13, 12, 30)

        result = sync_daily_note(client, articles, ts)
        assert result is True

        content = daily_path.read_text()
        assert "## 08:00 更新" in content
        assert "## 12:30 更新" in content

    def test_empty_articles(self, client: ObsidianClient) -> None:
        client._degraded = True
        result = sync_daily_note(client, [])
        assert result is True


class TestDailyNoteRest:
    """REST API 模式每日笔记测试."""

    def test_rest_create_and_append(self, client: ObsidianClient) -> None:
        # 模拟 daily note 不存在 -> 然后追加
        articles = [_make_article("Test", True, 9.0)]
        ts = datetime(2026, 4, 13, 8, 30)

        get_response = httpx.Response(
            404, request=httpx.Request("GET", "https://127.0.0.1:27124/v0/vault/AI-News/Daily/2026-04-13.md")
        )
        put_response = httpx.Response(
            204, request=httpx.Request("PUT", "https://127.0.0.1:27124/v0/vault/AI-News/Daily/2026-04-13.md")
        )
        patch_response = httpx.Response(
            204, request=httpx.Request("PATCH", "https://127.0.0.1:27124/v0/periodic/daily/")
        )

        call_count = 0
        original_request = client._client.request

        def mock_request(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return get_response
            elif call_count == 2:
                return put_response
            else:
                return patch_response

        with patch.object(client._client, "request", side_effect=mock_request):
            result = sync_daily_note(client, articles, ts)

        assert result is True

    def test_rest_fallback_to_filesystem(self, client: ObsidianClient, tmp_path: Path) -> None:
        """REST API 追加失败时降级到文件系统."""
        articles = [_make_article("Test", True, 9.0)]
        ts = datetime(2026, 4, 13, 8, 30)

        get_response = httpx.Response(
            200, text="existing", request=httpx.Request("GET", "https://127.0.0.1:27124/v0/vault/test")
        )
        patch_response = httpx.Response(
            500, request=httpx.Request("PATCH", "https://127.0.0.1:27124/v0/periodic/daily/")
        )

        call_count = 0

        def mock_request(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return get_response
            return patch_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("ainews.publisher.obsidian_client.time.sleep"):
                result = sync_daily_note(client, articles, ts)

        # 应降级为文件系统
        assert result is True
        file_path = tmp_path / "AI-News" / "Daily" / "2026-04-13.md"
        assert file_path.exists()


class TestDailyHeader:
    """每日笔记头部测试."""

    def test_header_contains_dataview(self) -> None:
        header = render_daily_header("2026-04-13")
        assert "# AI News - 2026-04-13" in header
        assert "```dataview" in header
        assert "SORT trend_score DESC" in header


def _make_article(title: str, trending: bool, relevance: float) -> object:
    """创建简易文章对象."""
    from types import SimpleNamespace
    return SimpleNamespace(
        title=title,
        is_trending=trending,
        relevance=relevance,
        category="industry",
        published_at=datetime(2026, 4, 13),
    )

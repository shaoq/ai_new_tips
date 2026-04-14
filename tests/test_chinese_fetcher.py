"""测试中文 AI 媒体采集器 — RSS 解析、网页解析、时间解析、容错、水印."""

from __future__ import annotations

import time as _time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.config.settings import ChineseConfig, ChineseSourceConfig
from ainews.fetcher.chinese import ChineseFetcher, _get_selectors


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_config(
    sources: list[dict[str, str]] | None = None,
) -> ChineseConfig:
    """快速构造 ChineseConfig."""
    if sources is None:
        sources = [
            {"name": "qbitai", "url": "https://www.qbitai.com/feed", "method": "rss"},
        ]
    return ChineseConfig(
        sources=[ChineseSourceConfig(**s) for s in sources],
    )


@pytest.fixture
def fetcher() -> ChineseFetcher:
    cfg = _make_config()
    return ChineseFetcher(config=cfg)


@pytest.fixture
def multi_source_fetcher() -> ChineseFetcher:
    cfg = _make_config(
        sources=[
            {"name": "qbitai", "url": "https://www.qbitai.com/feed", "method": "rss"},
            {"name": "jiqizhixin", "url": "https://www.jiqizhixin.com/", "method": "scrape"},
            {"name": "aibase", "url": "https://www.aibase.com/news", "method": "scrape"},
        ],
    )
    return ChineseFetcher(config=cfg)


# ------------------------------------------------------------------
# 测试 _get_selectors
# ------------------------------------------------------------------


class TestGetSelectors:
    def test_known_source_qbitai(self) -> None:
        sel = _get_selectors("qbitai")
        assert "container" in sel
        assert "title" in sel
        assert sel["container"] == "article.post, .article-item, .post-item"

    def test_known_source_jiqizhixin(self) -> None:
        sel = _get_selectors("jiqizhixin")
        assert "container" in sel
        assert sel["container"] == "article, .article-item, .article_content"

    def test_known_source_aibase(self) -> None:
        sel = _get_selectors("aibase")
        assert "container" in sel

    def test_unknown_source_falls_back(self) -> None:
        sel = _get_selectors("unknown_site")
        assert "container" in sel
        # 通用选择器包含 article
        assert "article" in sel["container"]


# ------------------------------------------------------------------
# 测试 RSS 模式
# ------------------------------------------------------------------


class TestRSSMode:
    def test_fetch_rss_basic(self, fetcher: ChineseFetcher) -> None:
        """RSS 模式基本解析."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>量子位</title>
            <item>
              <title>GPT-5 模型发布</title>
              <link>https://www.qbitai.com/2026/04/gpt5</link>
              <description>GPT-5 带来更强的推理能力</description>
              <pubDate>Mon, 14 Apr 2026 08:00:00 +0000</pubDate>
              <author>编辑部</author>
            </item>
            <item>
              <title>Claude 5 评测</title>
              <link>https://www.qbitai.com/2026/04/claude5</link>
              <description>Claude 5 各项基准测试表现优异</description>
              <pubDate>Mon, 13 Apr 2026 10:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/feed",
            method="rss",
        )
        items = fetcher._fetch_rss(source_cfg, since_ts=0.0)

        assert len(items) == 2
        assert items[0]["title"] == "GPT-5 模型发布"
        assert items[0]["url"] == "https://www.qbitai.com/2026/04/gpt5"
        assert items[0]["source"] == "chinese"
        assert items[0]["source_name"] == "qbitai"
        assert items[0]["author"] == "编辑部"
        assert items[0]["content_raw"] == "GPT-5 带来更强的推理能力"
        assert items[1]["title"] == "Claude 5 评测"

    def test_fetch_rss_since_filter(self, fetcher: ChineseFetcher) -> None:
        """RSS 模式增量过滤."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>旧文章</title>
              <link>https://example.com/old</link>
              <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate>
            </item>
            <item>
              <title>新文章</title>
              <link>https://example.com/new</link>
              <pubDate>Mon, 14 Apr 2026 08:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="test", url="https://example.com/feed", method="rss",
        )

        # since_ts = 2025-01-01 — 应过滤掉旧文章
        since_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        items = fetcher._fetch_rss(source_cfg, since_ts=since_dt.timestamp())

        assert len(items) == 1
        assert items[0]["title"] == "新文章"

    def test_fetch_rss_skip_no_link(self, fetcher: ChineseFetcher) -> None:
        """RSS 模式跳过没有 link 的条目."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>无链接文章</title>
              <description>这篇文章没有链接</description>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="test", url="https://example.com/feed", method="rss",
        )
        items = fetcher._fetch_rss(source_cfg, since_ts=0.0)
        assert len(items) == 0

    def test_fetch_rss_empty_feed(self, fetcher: ChineseFetcher) -> None:
        """RSS 空订阅."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>空 Feed</title>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="test", url="https://example.com/feed", method="rss",
        )
        items = fetcher._fetch_rss(source_cfg, since_ts=0.0)
        assert len(items) == 0

    def test_fetch_rss_uses_description_fallback(self, fetcher: ChineseFetcher) -> None:
        """RSS 条目无 summary 时使用 description."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>仅有描述</title>
              <link>https://example.com/desc</link>
              <description>这是描述内容</description>
              <pubDate>Mon, 14 Apr 2026 08:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="test", url="https://example.com/feed", method="rss",
        )
        items = fetcher._fetch_rss(source_cfg, since_ts=0.0)
        assert len(items) == 1
        assert items[0]["content_raw"] == "这是描述内容"


# ------------------------------------------------------------------
# 测试 Scrape 模式
# ------------------------------------------------------------------


class TestScrapeMode:
    def test_fetch_scrape_basic(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式基本解析."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="/articles/2026/04/gpt5-release">GPT-5 正式发布</a></h2>
          <p class="post-excerpt">OpenAI 发布了 GPT-5 模型</p>
          <time datetime="2026-04-14T08:00:00+00:00">2026-04-14</time>
        </article>
        <article class="post-item">
          <h2><a href="/articles/2026/04/claude5-review">Claude 5 深度评测</a></h2>
          <p class="post-excerpt">Anthropic 的 Claude 5 表现如何</p>
          <time datetime="2026-04-13T10:00:00+00:00">2026-04-13</time>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)

        assert len(items) == 2
        assert items[0]["title"] == "GPT-5 正式发布"
        assert items[0]["url"] == "https://www.qbitai.com/articles/2026/04/gpt5-release"
        assert items[0]["content_raw"] == "OpenAI 发布了 GPT-5 模型"
        assert items[0]["source"] == "chinese"
        assert items[0]["source_name"] == "qbitai"
        assert items[1]["title"] == "Claude 5 深度评测"

    def test_fetch_scrape_relative_url(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式相对 URL 补全."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="/news/123">测试文章</a></h2>
          <p>摘要内容</p>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)

        assert len(items) == 1
        assert items[0]["url"] == "https://www.qbitai.com/news/123"

    def test_fetch_scrape_absolute_url_unchanged(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式绝对 URL 保持不变."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="https://other.site.com/article">外部链接文章</a></h2>
          <p>摘要</p>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)

        assert len(items) == 1
        assert items[0]["url"] == "https://other.site.com/article"

    def test_fetch_scrape_skip_no_title_element(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式跳过没有标题元素的容器."""
        html = """
        <html><body>
        <article class="post-item">
          <p>这个容器没有标题</p>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)
        assert len(items) == 0

    def test_fetch_scrape_skip_empty_title(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式跳过空标题."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="https://example.com/article">  </a></h2>
          <p>摘要</p>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)
        assert len(items) == 0

    def test_fetch_scrape_skip_no_href(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式跳过没有 href 的标题链接."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a>没有链接的文章</a></h2>
          <p>摘要</p>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)
        assert len(items) == 0

    def test_fetch_scrape_since_filter(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式增量过滤."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="https://example.com/old">旧文章</a></h2>
          <time datetime="2024-01-01T00:00:00+00:00">2024-01-01</time>
        </article>
        <article class="post-item">
          <h2><a href="https://example.com/new">新文章</a></h2>
          <time datetime="2026-04-14T08:00:00+00:00">2026-04-14</time>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )

        since_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        items = fetcher._fetch_scrape(source_cfg, since_ts=since_dt.timestamp())

        assert len(items) == 1
        assert items[0]["title"] == "新文章"

    def test_fetch_scrape_empty_page(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式空页面."""
        html = "<html><body><p>没有文章</p></body></html>"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)
        assert len(items) == 0

    def test_fetch_scrape_no_summary(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式没有摘要时 content_raw 为空字符串."""
        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="https://example.com/article">没有摘要的文章</a></h2>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="qbitai",
            url="https://www.qbitai.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)
        assert len(items) == 1
        assert items[0]["content_raw"] == ""

    def test_fetch_scrape_jiqizhixin_selectors(self, fetcher: ChineseFetcher) -> None:
        """Scrape 模式使用 jiqizhixin 选择器."""
        html = """
        <html><body>
        <div class="article-item">
          <h2><a href="https://jiqizhixin.com/article/1">深度学习新突破</a></h2>
          <div class="article-des">新的神经网络架构</div>
          <span class="date">2026-04-14</span>
        </div>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        source_cfg = ChineseSourceConfig(
            name="jiqizhixin",
            url="https://www.jiqizhixin.com/",
            method="scrape",
        )
        items = fetcher._fetch_scrape(source_cfg, since_ts=0.0)

        assert len(items) == 1
        assert items[0]["title"] == "深度学习新突破"
        assert items[0]["content_raw"] == "新的神经网络架构"


# ------------------------------------------------------------------
# 测试 _normalize (通过 fetch_items 检查输出结构)
# ------------------------------------------------------------------


class TestNormalize:
    def test_rss_output_structure(self, fetcher: ChineseFetcher) -> None:
        """RSS 输出包含所有必要字段."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>测试文章</title>
              <link>https://example.com/test</link>
              <description>摘要内容</description>
              <pubDate>Mon, 14 Apr 2026 08:00:00 +0000</pubDate>
              <author>测试作者</author>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        # Patch time.sleep to avoid delay
        with patch("ainews.fetcher.chinese.time.sleep"):
            items = fetcher.fetch_items(since=None)

        assert len(items) == 1
        item = items[0]
        required_keys = {"url", "title", "content_raw", "source", "source_name"}
        assert required_keys.issubset(item.keys())
        assert item["source"] == "chinese"
        assert item["source_name"] == "qbitai"
        assert item["author"] == "测试作者"

    def test_scrape_output_structure(self, fetcher: ChineseFetcher) -> None:
        """Scrape 输出包含所有必要字段."""
        cfg = _make_config(
            sources=[
                {"name": "qbitai", "url": "https://www.qbitai.com/", "method": "scrape"},
            ],
        )
        f = ChineseFetcher(config=cfg)

        html = """
        <html><body>
        <article class="post-item">
          <h2><a href="https://example.com/article">文章标题</a></h2>
          <p class="post-excerpt">摘要</p>
          <time datetime="2026-04-14T08:00:00+00:00">2026-04-14</time>
        </article>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        f._client = mock_client

        with patch("ainews.fetcher.chinese.time.sleep"):
            items = f.fetch_items(since=None)

        assert len(items) == 1
        item = items[0]
        required_keys = {"url", "title", "content_raw", "source", "source_name"}
        assert required_keys.issubset(item.keys())
        assert item["source"] == "chinese"
        assert item["author"] == ""


# ------------------------------------------------------------------
# 测试 _build_cursor
# ------------------------------------------------------------------


class TestBuildCursor:
    def test_build_cursor_returns_max_time(self, fetcher: ChineseFetcher) -> None:
        items = [
            {"url": "https://a.com", "time": "2026-04-12T08:00:00+00:00"},
            {"url": "https://b.com", "time": "2026-04-14T10:00:00+00:00"},
            {"url": "https://c.com", "time": "2026-04-13T09:00:00+00:00"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-14T10:00:00+00:00"

    def test_build_cursor_empty(self, fetcher: ChineseFetcher) -> None:
        cursor = fetcher._build_cursor([])
        assert cursor is None

    def test_build_cursor_items_without_time(self, fetcher: ChineseFetcher) -> None:
        items = [
            {"url": "https://a.com", "time": ""},
            {"url": "https://b.com"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor is None

    def test_build_cursor_single_item(self, fetcher: ChineseFetcher) -> None:
        items = [
            {"url": "https://a.com", "time": "2026-04-14T08:00:00+00:00"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-14T08:00:00+00:00"

    def test_build_cursor_mixed_with_empty_time(self, fetcher: ChineseFetcher) -> None:
        items = [
            {"url": "https://a.com", "time": ""},
            {"url": "https://b.com", "time": "2026-04-14T08:00:00+00:00"},
            {"url": "https://c.com"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-14T08:00:00+00:00"


# ------------------------------------------------------------------
# 测试容错：一个源失败，其他源继续
# ------------------------------------------------------------------


class TestFaultTolerance:
    def test_one_source_fails_others_continue(
        self, multi_source_fetcher: ChineseFetcher,
    ) -> None:
        """单个源抛异常，不影响其他源."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>RSS 文章</title>
              <link>https://example.com/rss-article</link>
              <pubDate>Mon, 14 Apr 2026 08:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>"""

        rss_resp = MagicMock()
        rss_resp.status_code = 200
        rss_resp.text = rss_xml
        rss_resp.raise_for_status = MagicMock()

        scrape_resp = MagicMock()
        scrape_resp.status_code = 200
        scrape_resp.text = """
        <html><body>
        <article class="article-item">
          <h2><a href="https://example.com/scrape-article">Scrape 文章</a></h2>
          <div class="article-des">内容</div>
        </article>
        </body></html>
        """
        scrape_resp.raise_for_status = MagicMock()

        error_resp = MagicMock()
        error_resp.status_code = 500
        error_resp.raise_for_status.side_effect = Exception("HTTP 500")

        # qbitai=RSS(ok), jiqizhixin=scrape(error), aibase=scrape(ok)
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            rss_resp,       # qbitai RSS
            error_resp,     # jiqizhixin scrape - fails
            scrape_resp,    # aibase scrape
        ]
        multi_source_fetcher._client = mock_client

        with patch("ainews.fetcher.chinese.time.sleep"):
            items = multi_source_fetcher.fetch_items(since=None)

        # 应该拿到 qbitai 和 aibase 的结果，jiqizhixin 失败被跳过
        assert len(items) == 2
        sources = {item["source_name"] for item in items}
        assert "qbitai" in sources
        assert "aibase" in sources
        assert "jiqizhixin" not in sources

    def test_all_sources_fail(self, fetcher: ChineseFetcher) -> None:
        """所有源失败时返回空列表."""
        cfg = _make_config(
            sources=[
                {"name": "src1", "url": "https://fail1.com", "method": "rss"},
                {"name": "src2", "url": "https://fail2.com", "method": "rss"},
            ],
        )
        f = ChineseFetcher(config=cfg)

        mock_client = MagicMock()
        error_resp = MagicMock()
        error_resp.raise_for_status.side_effect = Exception("Connection refused")
        mock_client.get.return_value = error_resp
        f._client = mock_client

        with patch("ainews.fetcher.chinese.time.sleep"):
            items = f.fetch_items(since=None)

        assert items == []

    def test_source_with_empty_url_skipped(self, fetcher: ChineseFetcher) -> None:
        """URL 为空的源被跳过."""
        cfg = _make_config(
            sources=[
                {"name": "no_url", "url": "", "method": "rss"},
                {"name": "valid", "url": "https://example.com/feed", "method": "rss"},
            ],
        )
        f = ChineseFetcher(config=cfg)

        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item><title>OK</title><link>https://example.com/ok</link>
          <pubDate>Mon, 14 Apr 2026 08:00:00 +0000</pubDate></item>
        </channel></rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        f._client = mock_client

        with patch("ainews.fetcher.chinese.time.sleep"):
            items = f.fetch_items(since=None)

        # Only "valid" source fetched
        assert len(items) == 1
        assert items[0]["source_name"] == "valid"


# ------------------------------------------------------------------
# 测试 _parse_html_time
# ------------------------------------------------------------------


class TestParseHtmlTime:
    def test_iso_datetime_attribute(self) -> None:
        """datetime 属性 ISO 格式."""
        el = MagicMock()
        el.get.return_value = "2026-04-14T08:30:00+00:00"
        el.get_text.return_value = ""

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 14

    def test_iso_date_attribute_with_z(self) -> None:
        """datetime 属性带 Z 后缀."""
        el = MagicMock()
        el.get.return_value = "2026-04-14T08:30:00Z"
        el.get_text.return_value = ""

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 14

    def test_text_yyyy_mm_dd(self) -> None:
        """文本格式 YYYY-MM-DD."""
        el = MagicMock()
        el.get.return_value = ""
        el.get_text.return_value = "2026-04-14"

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 14

    def test_text_yyyy_mm_dd_hh_mm_ss(self) -> None:
        """文本格式 YYYY-MM-DD HH:MM:SS."""
        el = MagicMock()
        el.get.return_value = ""
        el.get_text.return_value = "2026-04-14 10:30:00"

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        assert result.year == 2026
        assert result.hour == 10
        assert result.minute == 30

    def test_text_chinese_date(self) -> None:
        """文本格式 YYYY年MM月DD日."""
        el = MagicMock()
        el.get.return_value = ""
        el.get_text.return_value = "2026年04月14日"

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 14

    def test_text_slash_date(self) -> None:
        """文本格式 YYYY/MM/DD."""
        el = MagicMock()
        el.get.return_value = ""
        el.get_text.return_value = "2026/04/14"

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 14

    def test_invalid_datetime_returns_none(self) -> None:
        """无法解析的时间返回 None."""
        el = MagicMock()
        el.get.return_value = "not-a-date"
        el.get_text.return_value = "完全无法识别的日期文字"

        result = ChineseFetcher._parse_html_time(el)
        assert result is None

    def test_empty_element_returns_none(self) -> None:
        """空元素返回 None."""
        el = MagicMock()
        el.get.return_value = ""
        el.get_text.return_value = ""

        result = ChineseFetcher._parse_html_time(el)
        assert result is None

    def test_datetime_attribute_priority_over_text(self) -> None:
        """datetime 属性优先于文本."""
        el = MagicMock()
        el.get.return_value = "2026-01-01T00:00:00+00:00"
        el.get_text.return_value = "2026-12-31"

        result = ChineseFetcher._parse_html_time(el)
        assert result is not None
        # 应该用 datetime 属性的值，不是文本
        assert result.month == 1
        assert result.day == 1


# ------------------------------------------------------------------
# 测试 _parse_feed_time
# ------------------------------------------------------------------


class TestParseFeedTime:
    def test_published_parsed(self) -> None:
        """published_parsed 时间解析."""
        # time.struct_time: (year, month, day, hour, min, sec, wday, yday, dst)
        entry = SimpleNamespace(
            published_parsed=_time.struct_time((2026, 4, 14, 8, 0, 0, 0, 104, -1)),
            updated_parsed=None,
        )
        result = ChineseFetcher._parse_feed_time(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 14

    def test_updated_parsed_fallback(self) -> None:
        """published_parsed 不存在时使用 updated_parsed."""
        entry = SimpleNamespace(
            published_parsed=None,
            updated_parsed=_time.struct_time((2026, 4, 13, 10, 30, 0, 0, 103, -1)),
        )
        result = ChineseFetcher._parse_feed_time(entry)
        assert result is not None
        assert result.month == 4
        assert result.day in (13, 14)  # mktime timezone 转换可能有 ±1 天

    def test_no_time_returns_none(self) -> None:
        """没有时间属性返回 None."""
        entry = SimpleNamespace(
            published_parsed=None,
            updated_parsed=None,
        )
        result = ChineseFetcher._parse_feed_time(entry)
        assert result is None


# ------------------------------------------------------------------
# 测试 test_connection
# ------------------------------------------------------------------


class TestConnection:
    def test_all_sources_ok(self, multi_source_fetcher: ChineseFetcher) -> None:
        """所有源连通正常."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch.object(multi_source_fetcher, "_client", mock_client), \
             patch("ainews.fetcher.chinese.time.monotonic", return_value=0):
            multi_source_fetcher._client = mock_client
            result = multi_source_fetcher.test_connection()

        assert result["ok"] is True
        assert "detail" in result

    def test_partial_sources_ok(self, fetcher: ChineseFetcher) -> None:
        """部分源连通."""
        cfg = _make_config(
            sources=[
                {"name": "ok_src", "url": "https://ok.com", "method": "rss"},
                {"name": "fail_src", "url": "https://fail.com", "method": "rss"},
            ],
        )
        f = ChineseFetcher(config=cfg)

        ok_resp = MagicMock()
        ok_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.get.side_effect = [ok_resp, Exception("Connection refused")]
        f._client = mock_client

        with patch("ainews.fetcher.chinese.time.monotonic", return_value=0):
            result = f.test_connection()

        assert result["ok"] is True
        assert "部分可用" in result["detail"]

    def test_all_sources_fail(self, fetcher: ChineseFetcher) -> None:
        """所有源不可达."""
        cfg = _make_config(
            sources=[
                {"name": "fail1", "url": "https://fail1.com", "method": "rss"},
                {"name": "fail2", "url": "https://fail2.com", "method": "rss"},
            ],
        )
        f = ChineseFetcher(config=cfg)

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Timeout")
        f._client = mock_client

        result = f.test_connection()
        assert result["ok"] is False
        assert "error" in result

    def test_no_sources_configured(self, fetcher: ChineseFetcher) -> None:
        """未配置任何源."""
        cfg = ChineseConfig(sources=[])
        f = ChineseFetcher(config=cfg)

        result = f.test_connection()
        assert result["ok"] is False
        assert "未配置" in result["error"]

    def test_http_non_200(self, fetcher: ChineseFetcher) -> None:
        """HTTP 非 200 状态码."""
        cfg = _make_config(
            sources=[
                {"name": "bad_src", "url": "https://bad.com", "method": "rss"},
            ],
        )
        f = ChineseFetcher(config=cfg)

        mock_resp = MagicMock()
        mock_resp.status_code = 403

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        f._client = mock_client

        result = f.test_connection()
        assert result["ok"] is False
        assert "403" in result["error"]


# ------------------------------------------------------------------
# 测试 _parse_since
# ------------------------------------------------------------------


class TestParseSince:
    def test_none_returns_zero(self, fetcher: ChineseFetcher) -> None:
        assert fetcher._parse_since(None) == 0.0

    def test_iso_string(self, fetcher: ChineseFetcher) -> None:
        ts = fetcher._parse_since("2026-04-14T00:00:00+00:00")
        assert ts > 0

    def test_iso_with_z(self, fetcher: ChineseFetcher) -> None:
        ts = fetcher._parse_since("2026-04-14T00:00:00Z")
        assert ts > 0

    def test_invalid_string_returns_zero(self, fetcher: ChineseFetcher) -> None:
        ts = fetcher._parse_since("not-a-date")
        assert ts == 0.0

    def test_empty_string_returns_zero(self, fetcher: ChineseFetcher) -> None:
        ts = fetcher._parse_since("")
        assert ts == 0.0


# ------------------------------------------------------------------
# 测试 _fetch_source 路由
# ------------------------------------------------------------------


class TestFetchSourceRouting:
    def test_rss_method_dispatches_to_fetch_rss(
        self, fetcher: ChineseFetcher,
    ) -> None:
        source_cfg = ChineseSourceConfig(
            name="test", url="https://example.com/feed", method="rss",
        )
        with patch.object(fetcher, "_fetch_rss", return_value=[]) as mock_rss:
            fetcher._fetch_source(source_cfg, since_ts=0.0)
            mock_rss.assert_called_once_with(source_cfg, 0.0)

    def test_scrape_method_dispatches_to_fetch_scrape(
        self, fetcher: ChineseFetcher,
    ) -> None:
        source_cfg = ChineseSourceConfig(
            name="test", url="https://example.com/", method="scrape",
        )
        with patch.object(fetcher, "_fetch_scrape", return_value=[]) as mock_scrape:
            fetcher._fetch_source(source_cfg, since_ts=0.0)
            mock_scrape.assert_called_once_with(source_cfg, 0.0)

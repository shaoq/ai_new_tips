"""ArXiv 采集器 — Atom XML API, cs.AI/cs.LG/cs.CL 分类监控."""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"

DEFAULT_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]

RATE_LIMIT_SECONDS = 3
DEFAULT_MAX_RESULTS = 50


class ArXivFetcher(BaseFetcher):
    """ArXiv 论文采集器.

    使用 ArXiv API 拉取指定分类的最新论文，遵守 1 req/3sec 速率限制.
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="arxiv", config=config)
        self._client = httpx.Client(timeout=60.0, follow_redirects=True)
        self.categories: list[str] = DEFAULT_CATEGORIES
        if config and hasattr(config, "arxiv_categories"):
            cats = getattr(config, "arxiv_categories", None)
            if cats:
                self.categories = cats

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """从 ArXiv API 拉取论文."""
        search_query = self._build_search_query()
        params: dict[str, Any] = {
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": DEFAULT_MAX_RESULTS,
        }

        # 增量水印：添加提交日期过滤
        if since:
            params["start"] = 0
            # ArXiv 不直接支持 submittedDate 过滤，我们在结果中过滤

        all_items: list[dict[str, Any]] = []
        start = 0
        max_results = DEFAULT_MAX_RESULTS

        while True:
            params["start"] = start
            params["max_results"] = min(max_results, 200)

            logger.info("[arxiv] 请求 start=%d max_results=%d", start, params["max_results"])
            xml_data = self._request(params)
            if xml_data is None:
                break

            items, total = self._parse_atom(xml_data)
            if not items:
                break

            # 增量过滤
            if since:
                filtered = self._filter_by_since(items, since)
                all_items.extend(filtered)
                if len(filtered) < len(items):
                    # 有旧数据了，停止翻页
                    break
            else:
                all_items.extend(items)

            if len(all_items) >= total or len(items) < params["max_results"]:
                break

            start += params["max_results"]
            time.sleep(RATE_LIMIT_SECONDS)

        return all_items

    # ------------------------------------------------------------------
    # 查询构建
    # ------------------------------------------------------------------

    def _build_search_query(self) -> str:
        """构建 ArXiv 搜索查询字符串."""
        cat_parts = [f"cat:{cat}" for cat in self.categories]
        return " OR ".join(cat_parts)

    # ------------------------------------------------------------------
    # HTTP 请求
    # ------------------------------------------------------------------

    def _request(self, params: dict[str, Any]) -> Optional[str]:
        """发送 ArXiv API 请求."""
        try:
            time.sleep(RATE_LIMIT_SECONDS)
            resp = self._client.get(ARXIV_API, params=params)
            resp.raise_for_status()
            return resp.text
        except Exception:
            logger.error("[arxiv] 请求失败: params=%s", params, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Atom XML 解析
    # ------------------------------------------------------------------

    def _parse_atom(self, xml_data: str) -> tuple[list[dict[str, Any]], int]:
        """解析 ArXiv Atom XML 响应."""
        items: list[dict[str, Any]] = []
        total = 0

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            logger.error("[arxiv] XML 解析失败")
            return items, total

        # totalResults
        ns = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
        opensearch_ns = "http://a9.com/-/spec/opensearch/1.1/"
        total_el = root.find(f"{{{opensearch_ns}}}totalResults")
        if total_el is not None and total_el.text:
            total = int(total_el.text)

        for entry in root.findall("atom:entry", ns):
            item = self._parse_entry(entry, ns)
            if item:
                items.append(item)

        return items, total

    def _parse_entry(
        self, entry: ET.Element, ns: dict[str, str]
    ) -> Optional[dict[str, Any]]:
        """解析单条 Atom entry."""
        title_el = entry.find("atom:title", ns)
        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""

        summary_el = entry.find("atom:summary", ns)
        content_raw = (summary_el.text or "").strip() if summary_el is not None else ""

        # authors
        authors: list[str] = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        # published
        published_el = entry.find("atom:published", ns)
        published_at: Optional[datetime] = None
        if published_el is not None and published_el.text:
            published_at = self._parse_arxiv_date(published_el.text.strip())

        # links — 优先 HTML 页面链接
        url = ""
        categories: list[str] = []
        for link_el in entry.findall("atom:link", ns):
            link_type = link_el.get("type", "")
            link_href = link_el.get("href", "")
            if link_type == "text/html" and link_href:
                url = link_href
            elif "title" in link_el.attrib and link_el.get("title") == "pdf" and not url:
                url = link_href

        # 如果没有找到 HTML/PDF 链接，使用 arxiv id 构造
        id_el = entry.find("atom:id", ns)
        if not url and id_el is not None and id_el.text:
            url = id_el.text.strip()

        # categories
        for cat_el in entry.findall("atom:category", ns):
            term = cat_el.get("term", "")
            if term:
                categories.append(term)

        if not url:
            return None

        return {
            "url": url,
            "title": title,
            "content_raw": content_raw,
            "source": "arxiv",
            "source_name": "ArXiv",
            "author": ", ".join(authors),
            "category": ", ".join(categories),
            "published_at": published_at,
        }

    @staticmethod
    def _parse_arxiv_date(date_str: str) -> Optional[datetime]:
        """解析 ArXiv 日期格式."""
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # 增量过滤
    # ------------------------------------------------------------------

    def _filter_by_since(
        self, items: list[dict[str, Any]], since: str
    ) -> list[dict[str, Any]]:
        """根据水印过滤旧条目."""
        try:
            since_date = datetime.fromisoformat(since)
            if since_date.tzinfo is None:
                since_date = since_date.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return items

        filtered: list[dict[str, Any]] = []
        for item in items:
            pub = item.get("published_at")
            if pub is None:
                filtered.append(item)
                continue
            if isinstance(pub, datetime):
                pub_aware = pub.replace(tzinfo=timezone.utc) if pub.tzinfo is None else pub
                if pub_aware > since_date:
                    filtered.append(item)
            else:
                filtered.append(item)

        return filtered

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最新论文的 published_at 作为水印."""
        if not items:
            return None
        dates: list[datetime] = []
        for item in items:
            pub = item.get("published_at")
            if isinstance(pub, datetime):
                dates.append(pub)
        if dates:
            latest = max(dates)
            return latest.isoformat()
        return None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试 ArXiv API 连通性."""
        try:
            start = time.monotonic()
            params = {
                "search_query": "cat:cs.AI",
                "max_results": 1,
            }
            time.sleep(RATE_LIMIT_SECONDS)
            resp = self._client.get(ARXIV_API, params=params, timeout=30)
            latency = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                entries = root.findall(f"{{{ATOM_NS}}}entry")
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "detail": f"连接成功，返回 {len(entries)} 条结果",
                }
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

"""URL 标准化与 hash 计算."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import ParseResult, urlparse, urlunparse

# 常见的 tracking 参数前缀
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "source", "mc_eid", "_ga")


def normalize_url(url: str) -> str:
    """标准化 URL：移除 www、trailing slash、tracking 参数.

    步骤：
    1. 解析 URL
    2. 移除 scheme（http/https 差异不影响内容）
    3. 移除 www 前缀
    4. 移除 tracking 参数（utm_* 等）
    5. 排序剩余查询参数（保证顺序一致）
    6. 移除 trailing slash
    7. 转为小写 hostname
    8. 移除 fragment（#锚点）

    返回标准化后的 URL 字符串。
    """
    if not url or not url.strip():
        return ""

    url = url.strip()

    parsed: ParseResult = urlparse(url)

    # 移除 www 前缀，hostname 转小写
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # 保留端口
    port = f":{parsed.port}" if parsed.port else ""

    # 处理路径：移除 trailing slash（但保留 root path "/"）
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # 过滤 tracking 参数并排序
    clean_query = _filter_tracking_params(parsed.query)

    netloc = f"{hostname}{port}"
    scheme = parsed.scheme

    clean_url = urlunparse((scheme, netloc, path, parsed.params, clean_query, ""))

    return clean_url


def _filter_tracking_params(query: str) -> str:
    """从查询字符串中移除 tracking 参数.

    参数:
        query: URL 查询字符串（不含 ?）

    返回:
        过滤并排序后的查询字符串
    """
    if not query:
        return ""

    params: list[tuple[str, str]] = []
    for part in query.split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
        else:
            key, value = part, ""
        # 跳过 tracking 参数
        if any(key.lower().startswith(prefix) for prefix in _TRACKING_PREFIXES):
            continue
        params.append((key, value))

    if not params:
        return ""

    # 按键名排序保证一致性
    params.sort(key=lambda p: p[0])
    return "&".join(f"{k}={v}" for k, v in params)


def compute_url_hash(url: str) -> str:
    """对标准化 URL 计算 SHA256 hash.

    用于快速查重比较。
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def urls_match(url_a: str, url_b: str) -> bool:
    """判断两个 URL 标准化后是否相同."""
    return normalize_url(url_a) == normalize_url(url_b)

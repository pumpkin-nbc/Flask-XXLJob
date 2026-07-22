"""
URL 辅助函数。

URL helper functions.
"""

from __future__ import annotations


def join_url(base: str, path: str) -> str:
    """
    拼接 Admin 基础地址与 API 路径，避免出现重复或缺失斜杠。

    - 去除 base 尾部与 path 首部多余的斜杠。
    - 兼容带路径的 base（例如 ``http://host/xxl-job-admin``）。
    - path 为空时返回去除尾斜杠的 base。

    Join an admin base address with an API path without producing duplicate or
    missing slashes.

    - Strips redundant trailing slashes on ``base`` and leading slashes on
      ``path``.
    - Compatible with a ``base`` that carries a path (e.g.
      ``http://host/xxl-job-admin``).
    - Returns the trimmed ``base`` when ``path`` is empty.
    """
    trimmed_base = base.rstrip("/")
    trimmed_path = path.strip("/")
    if not trimmed_path:
        return trimmed_base
    return trimmed_base + "/" + trimmed_path

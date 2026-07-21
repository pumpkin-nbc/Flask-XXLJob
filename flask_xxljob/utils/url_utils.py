"""
URL 辅助函数。

URL helper functions.
"""

from __future__ import annotations


def join_url(base: str, path: str) -> str:
    """
    拼接 Admin 基础地址与 API 路径，避免出现重复斜杠。

    Join an admin base address with an API path without producing duplicate
    slashes.
    """
    return base.rstrip("/") + "/" + path.lstrip("/")

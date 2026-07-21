"""
JSON 辅助函数。

JSON helper functions.
"""

from __future__ import annotations

import json
from typing import Any


def try_parse_json(value: str) -> Any:
    """
    尝试将字符串解析为 JSON。

    - 空字符串或纯空白返回 ``None``。
    - 合法 JSON 返回对应 Python 对象。
    - 非 JSON 返回原始字符串。

    Try to parse a string as JSON.

    - A blank or whitespace-only string returns ``None``.
    - Valid JSON returns the corresponding Python object.
    - Otherwise the original string is returned unchanged.
    """
    if value is None:
        return None
    if not value.strip():
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def dumps(value: Any) -> str:
    """
    将对象序列化为紧凑的 JSON 字符串。

    Serialize an object into a compact JSON string.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

"""
执行器请求体解析。

Executor request-body parsing.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple


class RequestParseError(Exception):
    """
    请求体无法解析或超出大小限制时抛出。

    Raised when the request body cannot be parsed or exceeds a size limit.
    """


def parse_json_body(raw_body: bytes, max_request_size: int) -> Any:
    """
    解析 JSON 请求体并校验整体大小。

    Parse a JSON request body and validate its overall size.
    """
    if raw_body is None:
        return {}
    if len(raw_body) > max_request_size:
        raise RequestParseError("request body exceeds the maximum allowed size")
    if not raw_body:
        return {}
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RequestParseError(f"invalid JSON request body: {type(exc).__name__}") from exc


def check_param_length(data: Any, max_param_length: int) -> Optional[str]:
    """
    校验 ``executorParams`` 长度，返回错误信息或 ``None``。

    Validate the length of ``executorParams``; return an error message or
    ``None``.
    """
    if isinstance(data, dict):
        params = data.get("executorParams")
        if isinstance(params, str) and len(params) > max_param_length:
            return "executorParams exceeds the maximum allowed length"
    return None


def parse_and_validate(
    raw_body: bytes, max_request_size: int, max_param_length: int
) -> Tuple[Any, Optional[str]]:
    """
    解析请求体并校验参数长度。

    Parse the request body and validate parameter length.
    """
    data = parse_json_body(raw_body, max_request_size)
    error = check_param_length(data, max_param_length)
    return data, error

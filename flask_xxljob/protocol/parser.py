"""
执行器请求体解析。

Executor request-body parsing.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple


class RequestParseError(Exception):
    """
    请求体无法解析、为空、不是 JSON 对象或超出大小限制时抛出。

    Raised when the request body cannot be parsed, is empty, is not a JSON
    object, or exceeds the size limit.
    """


def _read_limited_body(
    stream: Any, content_length: Optional[int], max_request_size: int
) -> bytes:
    """
    最多从请求流读取 ``max_request_size + 1`` 字节。

    Read at most ``max_request_size + 1`` bytes from a request stream.

    A known oversized ``Content-Length`` is rejected before reading. For
    streams without a known length, the extra byte detects an oversized body
    without buffering the complete request in memory.
    """
    if content_length is not None and content_length > max_request_size:
        raise RequestParseError("request body exceeds the maximum allowed size")

    remaining = max_request_size + 1
    chunks = []
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)

    raw_body = b"".join(chunks)
    if len(raw_body) > max_request_size:
        raise RequestParseError("request body exceeds the maximum allowed size")
    return raw_body


def parse_json_object(raw_body: bytes, max_request_size: int) -> dict:
    """
    解析 JSON 请求体，要求其为 JSON 对象。

    - 空请求体返回明确错误。
    - 超过大小限制返回明确错误。
    - 非法 JSON 返回明确错误。
    - JSON 数组或标量（非对象）返回明确错误。

    Parse a JSON request body and require it to be a JSON object.

    - An empty body raises an explicit error.
    - A body exceeding the size limit raises an explicit error.
    - Invalid JSON raises an explicit error.
    - A JSON array or scalar (non-object) raises an explicit error.
    """
    if raw_body is None or len(raw_body) == 0:
        raise RequestParseError("request body is empty")
    if len(raw_body) > max_request_size:
        raise RequestParseError("request body exceeds the maximum allowed size")
    try:
        # 官方使用 UTF-8，且 Content-Type 可能带 charset，此处按 UTF-8 解码。
        # The official protocol uses UTF-8; the Content-Type may carry a charset,
        # so the body is decoded as UTF-8 here.
        data = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RequestParseError(f"invalid JSON request body: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise RequestParseError("request body must be a JSON object")
    return data


def check_param_length(data: dict, max_param_length: int) -> Optional[str]:
    """
    校验 ``executorParams`` 长度，返回错误信息或 ``None``。

    Validate the length of ``executorParams``; return an error message or
    ``None``.
    """
    params = data.get("executorParams")
    if isinstance(params, str) and len(params) > max_param_length:
        return "executorParams exceeds the maximum allowed length"
    return None


def parse_and_validate(
    raw_body: bytes, max_request_size: int, max_param_length: int
) -> Tuple[dict, Optional[str]]:
    """
    解析请求体（要求 JSON 对象）并校验参数长度。

    Parse the request body (requiring a JSON object) and validate parameter
    length.
    """
    data = parse_json_object(raw_body, max_request_size)
    error = check_param_length(data, max_param_length)
    return data, error


# 向后兼容别名 / Backward-compatible alias.
def parse_json_body(raw_body: bytes, max_request_size: int) -> Any:
    """
    解析 JSON 请求体（要求 JSON 对象）。

    Parse a JSON request body (requiring a JSON object).
    """
    return parse_json_object(raw_body, max_request_size)

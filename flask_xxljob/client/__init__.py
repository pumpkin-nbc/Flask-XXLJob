"""
Flask-XXLJob 与 XXL-JOB Admin 通信的 HTTP 客户端。

HTTP clients used by Flask-XXLJob to talk to the XXL-JOB admin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import requests

from ..response.executor import SUCCESS_CODE
from ..utils.url_utils import join_url

# 官方 Access Token 请求头名称 / Official access-token header name.
ACCESS_TOKEN_HEADER = "XXL-JOB-ACCESS-TOKEN"


@dataclass
class CallResult:
    """
    一次 Admin API 调用的结果。

    The result of a single admin API call.
    """

    success: bool
    code: Optional[int] = None
    msg: Optional[str] = None
    address: Optional[str] = None
    error: Optional[str] = None


def _build_headers(access_token: str) -> dict:
    headers = {"Content-Type": "application/json"}
    # 仅在配置了 Token 时才添加请求头，Token 不写入日志或异常信息。
    # Only add the header when a token is configured; the token is never
    # written to logs or exception messages.
    if access_token:
        headers[ACCESS_TOKEN_HEADER] = access_token
    return headers


def post_to_admins(
    admin_addresses: List[str],
    api_path: str,
    payload: Any,
    access_token: str,
    timeout: Tuple[int, int],
) -> CallResult:
    """
    依次向多个 Admin 地址发送 POST 请求，直到成功或全部失败。

    Send a POST request to multiple admin addresses in order until one
    succeeds or all of them fail.
    """
    headers = _build_headers(access_token)
    last_result = CallResult(success=False, error="no admin address configured")

    for address in admin_addresses:
        url = join_url(address, api_path)
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            # 不泄露 Token，仅记录异常类型与地址。
            # Do not leak the token; only record the exception type and address.
            last_result = CallResult(
                success=False,
                address=address,
                error=f"{type(exc).__name__}: {exc}",
            )
            continue

        if response.status_code != 200:
            last_result = CallResult(
                success=False,
                address=address,
                error=f"HTTP {response.status_code}",
            )
            continue

        try:
            body = response.json()
        except ValueError:
            last_result = CallResult(
                success=False,
                address=address,
                error="invalid JSON response",
            )
            continue

        code = body.get("code")
        msg = body.get("msg")
        if code == SUCCESS_CODE:
            return CallResult(success=True, code=code, msg=msg, address=address)

        last_result = CallResult(success=False, code=code, msg=msg, address=address)

    return last_result


__all__ = ["CallResult", "ACCESS_TOKEN_HEADER", "post_to_admins"]

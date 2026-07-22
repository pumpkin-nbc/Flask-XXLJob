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

    @property
    def message(self) -> Optional[str]:
        """
        规范化的结果信息：优先返回 Admin 的 ``msg``，否则返回本地 ``error``。

        Canonical result message: the admin ``msg`` when present, otherwise the
        local ``error``.
        """
        return self.msg if self.msg is not None else self.error

    @property
    def admin_address(self) -> Optional[str]:
        """
        产生该结果的 Admin 地址（``address`` 的别名）。

        The admin address that produced this result (alias of ``address``).
        """
        return self.address


# 规范名称别名：语义等同 CallResult，导出以便公开 API 使用。
# Canonical-name alias: semantically identical to CallResult, exported for the
# public API.
AdminCallResult = CallResult


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
    stop_on_business_response: bool = False,
) -> CallResult:
    """
    依次向多个 Admin 地址发送 POST 请求，直到成功或全部失败。

    - ``stop_on_business_response=False``（默认，用于注册/注销）：仅在业务成功时
      返回，业务失败会继续尝试下一个地址。
    - ``stop_on_business_response=True``（用于任务回调）：只要收到 Admin 的有效
      业务响应（无论成功或失败）即返回，避免向多个 Admin 重复发送同一回调；仅在
      网络错误、非 200 或非法 JSON 时才切换到下一个地址。

    Send a POST request to multiple admin addresses in order.

    - ``stop_on_business_response=False`` (default, for registration): returns
      only on business success; a business failure moves on to the next address.
    - ``stop_on_business_response=True`` (for task callbacks): returns as soon as
      any valid business response is received (success or failure) so that the
      same callback is not delivered to multiple admins; failover happens only on
      a network error, non-200 status, or invalid JSON.
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
        # 收到有效业务响应即停止，避免重复回调。
        # Stop on a valid business response to avoid duplicate callbacks.
        if stop_on_business_response:
            return last_result

    return last_result


__all__ = ["CallResult", "AdminCallResult", "ACCESS_TOKEN_HEADER", "post_to_admins"]

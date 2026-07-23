"""
Flask-XXLJob 与 XXL-JOB Admin 通信的 HTTP 客户端。

HTTP clients used by Flask-XXLJob to talk to the XXL-JOB admin.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import requests

from ..response.executor import SUCCESS_CODE
from ..utils.url_utils import join_url
from .policy import AdminCallPolicy

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
    error_type: Optional[str] = None
    attempt_count: int = 0
    elapsed_ms: Optional[int] = None
    http_status: Optional[int] = None

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


# 调用结果错误分类常量（见 needs 10.4）。
# Call-result error categories (see spec 10.4).
ERROR_CONFIG = "config"
ERROR_NETWORK = "network"
ERROR_TIMEOUT = "timeout"
ERROR_HTTP = "http"
ERROR_INVALID_JSON = "invalid_json"
ERROR_BUSINESS = "business"


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


# 可在同一地址重试的错误类型（瞬时错误）。
# Error types that may be retried on the same address (transient errors).
_RETRYABLE_ERROR_TYPES = frozenset({ERROR_NETWORK, ERROR_TIMEOUT, ERROR_HTTP})


def _should_failover(error_type: Optional[str], policy: AdminCallPolicy) -> bool:
    # 决定某类错误是否应切换到下一个 Admin 地址。
    # Decide whether a given error type should fail over to the next admin.
    if error_type in (ERROR_NETWORK, ERROR_TIMEOUT):
        return True
    if error_type == ERROR_HTTP:
        return policy.failover_on_http_error
    if error_type == ERROR_INVALID_JSON:
        return policy.failover_on_invalid_json
    if error_type == ERROR_BUSINESS:
        return policy.failover_on_business_error
    # ERROR_CONFIG 或未知：不切换。 / ERROR_CONFIG or unknown: no failover.
    return False


def post_to_admins(
    admin_addresses: List[str],
    api_path: str,
    payload: Any,
    access_token: str,
    timeout: Tuple[int, int],
    stop_on_business_response: bool = False,
    policy: Optional[AdminCallPolicy] = None,
    logger: Optional[logging.Logger] = None,
) -> CallResult:
    """
    依次向多个 Admin 地址发送 POST 请求，支持有限的同步重试与故障转移。

    对每个地址，最多重试 ``policy.retry_count`` 次（仅针对网络/超时/HTTP 等瞬时
    错误，重试之间按 ``policy.retry_backoff`` 秒同步等待）。是否在一类错误后切换到
    下一个地址由 ``policy`` 决定；网络与超时错误始终切换。返回的 :class:`CallResult`
    额外包含 ``attempt_count``（总请求次数）、``elapsed_ms``（总耗时）与
    ``http_status``（最近一次 HTTP 状态码）。Access Token 绝不写入结果或日志。

    当未显式提供 ``policy`` 时，采用与 0.1.2 完全一致的行为（不重试；网络/超时/
    HTTP/非法 JSON 均切换；业务失败是否切换取决于 ``stop_on_business_response``）。

    Send a POST request to multiple admin addresses in order, with bounded
    synchronous retry and failover.

    For each address the request is retried at most ``policy.retry_count`` times
    (only for transient network/timeout/HTTP errors, with a synchronous
    ``policy.retry_backoff`` second wait between attempts). Whether an error type
    fails over to the next address is governed by ``policy``; network and timeout
    errors always fail over. The returned :class:`CallResult` additionally
    carries ``attempt_count`` (total requests made), ``elapsed_ms`` (total
    elapsed time) and ``http_status`` (the most recent HTTP status). The access
    token is never written to the result or to logs.

    When no ``policy`` is supplied, behaviour is identical to 0.1.2 (no retry;
    network/timeout/HTTP/invalid-JSON all fail over; business failover depends on
    ``stop_on_business_response``).
    """
    if policy is None:
        # 复现 0.1.2 行为，保证直接调用者/旧测试不受影响。
        # Reproduce 0.1.2 behaviour so direct callers/old tests are unaffected.
        policy = AdminCallPolicy(
            retry_count=0,
            retry_backoff=0.0,
            failover_on_http_error=True,
            failover_on_invalid_json=True,
            failover_on_business_error=not stop_on_business_response,
        )

    headers = _build_headers(access_token)
    start = time.monotonic()
    attempts = 0
    last_result = CallResult(
        success=False,
        error="no admin address configured",
        error_type=ERROR_CONFIG,
    )

    def _elapsed_ms() -> int:
        return int((time.monotonic() - start) * 1000)

    for address in admin_addresses:
        url = join_url(address, api_path)

        # 单个地址内的有限重试（仅瞬时错误）。
        # Bounded retry within a single address (transient errors only).
        for attempt in range(policy.retry_count + 1):
            attempts += 1
            http_status: Optional[int] = None
            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=timeout
                )
            except requests.Timeout as exc:
                last_result = CallResult(
                    success=False,
                    address=address,
                    error=f"{type(exc).__name__}: {exc}",
                    error_type=ERROR_TIMEOUT,
                    attempt_count=attempts,
                    elapsed_ms=_elapsed_ms(),
                )
            except requests.RequestException as exc:
                # 网络失败。不泄露 Token，仅记录异常类型与地址。
                # Network failure. Do not leak the token; record type and address.
                last_result = CallResult(
                    success=False,
                    address=address,
                    error=f"{type(exc).__name__}: {exc}",
                    error_type=ERROR_NETWORK,
                    attempt_count=attempts,
                    elapsed_ms=_elapsed_ms(),
                )
            else:
                http_status = response.status_code
                if response.status_code != 200:
                    last_result = CallResult(
                        success=False,
                        address=address,
                        error=f"HTTP {response.status_code}",
                        error_type=ERROR_HTTP,
                        attempt_count=attempts,
                        elapsed_ms=_elapsed_ms(),
                        http_status=http_status,
                    )
                else:
                    try:
                        body = response.json()
                    except ValueError:
                        last_result = CallResult(
                            success=False,
                            address=address,
                            error="invalid JSON response",
                            error_type=ERROR_INVALID_JSON,
                            attempt_count=attempts,
                            elapsed_ms=_elapsed_ms(),
                            http_status=http_status,
                        )
                    else:
                        if not isinstance(body, dict):
                            last_result = CallResult(
                                success=False,
                                address=address,
                                error="JSON response body must be an object",
                                error_type=ERROR_INVALID_JSON,
                                attempt_count=attempts,
                                elapsed_ms=_elapsed_ms(),
                                http_status=http_status,
                            )
                        else:
                            code = body.get("code")
                            msg = body.get("msg")
                            if code == SUCCESS_CODE:
                                return CallResult(
                                    success=True,
                                    code=code,
                                    msg=msg,
                                    address=address,
                                    attempt_count=attempts,
                                    elapsed_ms=_elapsed_ms(),
                                    http_status=http_status,
                                )
                            last_result = CallResult(
                                success=False,
                                code=code,
                                msg=msg,
                                address=address,
                                error_type=ERROR_BUSINESS,
                                attempt_count=attempts,
                                elapsed_ms=_elapsed_ms(),
                                http_status=http_status,
                            )

            # 仅瞬时错误且仍有重试次数时，同步退避后重试同一地址。
            # Retry the same address (after synchronous backoff) only for a
            # transient error while retries remain.
            retryable = last_result.error_type in _RETRYABLE_ERROR_TYPES
            if retryable and attempt < policy.retry_count:
                if logger is not None:
                    logger.debug(
                        "Retrying Admin request address=%s error_type=%s "
                        "http_status=%s attempt=%s.",
                        address,
                        last_result.error_type,
                        last_result.http_status,
                        attempts,
                    )
                if policy.retry_backoff > 0:
                    time.sleep(policy.retry_backoff)
                continue
            break

        # 重试用尽后，按策略决定是否切换到下一个 Admin。
        # After retries are exhausted, decide failover per policy.
        if not _should_failover(last_result.error_type, policy):
            return last_result
        if logger is not None and address != admin_addresses[-1]:
            logger.warning(
                "Failing over to the next Admin address after "
                "address=%s error_type=%s http_status=%s.",
                address,
                last_result.error_type,
                last_result.http_status,
            )

    return last_result


__all__ = [
    "CallResult",
    "AdminCallResult",
    "AdminCallPolicy",
    "ACCESS_TOKEN_HEADER",
    "post_to_admins",
    "ERROR_CONFIG",
    "ERROR_NETWORK",
    "ERROR_TIMEOUT",
    "ERROR_HTTP",
    "ERROR_INVALID_JSON",
    "ERROR_BUSINESS",
]

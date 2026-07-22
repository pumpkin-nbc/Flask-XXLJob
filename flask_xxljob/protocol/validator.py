"""
执行器请求的 Access Token 与大小校验。

Access-token and size validation for executor requests.
"""

from __future__ import annotations

import hmac
from typing import Any, Optional

from ..client import ACCESS_TOKEN_HEADER

# 官方 Token 错误信息 / Official token error message.
ACCESS_TOKEN_ERROR = "The access token is wrong."


def check_access_token(configured_token: str, request_token: Optional[str]) -> bool:
    """
    校验请求携带的 Access Token。

    - 未配置 Token（空或纯空白）时按官方无 Token 模式处理，直接通过。
    - 配置了 Token 时，请求头必须与配置完全一致。

    Validate the access token carried by a request.

    - When no token is configured (empty or blank), the official no-token mode
      applies and the request passes.
    - When a token is configured, the request header must match exactly. The
      comparison uses :func:`hmac.compare_digest` for constant-time behaviour so
      the token cannot be recovered through timing. A missing or non-string
      header is safely rejected. The token is never logged or returned.
    """
    if not configured_token or not configured_token.strip():
        return True
    if not isinstance(request_token, str):
        return False
    # 以字节比较，兼容非 ASCII Token；compare_digest 对非 ASCII str 会报错。
    # Compare as bytes to support non-ASCII tokens; compare_digest raises on
    # non-ASCII str inputs.
    return hmac.compare_digest(
        configured_token.encode("utf-8"), request_token.encode("utf-8")
    )


def extract_request_token(headers: Any) -> Optional[str]:
    """
    从请求头中读取官方 Access Token。

    Read the official access token from request headers.
    """
    return headers.get(ACCESS_TOKEN_HEADER)

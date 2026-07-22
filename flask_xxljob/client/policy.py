"""
Admin 调用策略：有限、同步的重试与故障转移。

Admin call policy: bounded, synchronous retry and failover.

该策略只在单次同步调用内生效，不创建后台线程，不持久化失败请求，也不提供跨重启
恢复。重试次数和退避时间都有硬上限。

The policy only applies within a single synchronous call. It never creates a
background thread, never persists failed requests, and never provides
cross-restart recovery. Both the retry count and the backoff have hard caps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import XXLJobConfig

# 硬上限，避免无限循环或过长阻塞。
# Hard caps to prevent unbounded loops or excessive blocking.
RETRY_COUNT_CAP = 10
RETRY_BACKOFF_CAP = 30.0


@dataclass(frozen=True)
class AdminCallPolicy:
    """
    单次 Admin 调用的重试与故障转移策略。

    Retry and failover policy for a single admin call.
    """

    retry_count: int = 0
    retry_backoff: float = 0.0
    failover_on_http_error: bool = True
    failover_on_invalid_json: bool = False
    failover_on_business_error: bool = False

    @classmethod
    def from_config(cls, config: "XXLJobConfig") -> "AdminCallPolicy":
        """
        根据配置构造策略，并将重试次数与退避时间限制在硬上限内。

        Build a policy from configuration, clamping the retry count and backoff
        to their hard caps.
        """
        return cls(
            retry_count=max(0, min(config.admin_retry_count, RETRY_COUNT_CAP)),
            retry_backoff=max(0.0, min(config.admin_retry_backoff, RETRY_BACKOFF_CAP)),
            failover_on_http_error=config.admin_failover_on_http_error,
            failover_on_invalid_json=config.admin_failover_on_invalid_json,
            failover_on_business_error=config.admin_failover_on_business_error,
        )


__all__ = ["AdminCallPolicy", "RETRY_COUNT_CAP", "RETRY_BACKOFF_CAP"]

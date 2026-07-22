"""
Flask-XXLJob 插件运行状态模型。

Flask-XXLJob plugin runtime-status model.

该模型只描述 Flask-XXLJob 插件自身的状态（是否启用、是否自动注册、最近一次注册
结果等），绝不描述业务任务状态，也不包含 Access Token。

This model only describes the state of the Flask-XXLJob plugin itself (whether
it is enabled, whether auto-registration is on, the last registration result,
and so on). It never describes business-task state and never contains the
access token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class XXLJobStatus:
    """
    Flask-XXLJob 插件的只读运行状态快照。

    A read-only snapshot of the Flask-XXLJob plugin runtime status.
    """

    enabled: bool
    auto_register: bool
    registered: bool
    last_registry_time: Optional[str] = None
    last_registry_success: Optional[bool] = None
    last_registry_admin_address: Optional[str] = None
    last_registry_error_type: Optional[str] = None
    last_registry_message: Optional[str] = None
    registry_thread_running: bool = False


__all__ = ["XXLJobStatus"]

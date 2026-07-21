"""
保存 Flask 项目注册的 XXL-JOB 请求处理函数。

Stores the XXL-JOB request-callbacks registered by the Flask project.

此模块只保存请求处理函数，不保存任何业务任务状态。

This module only stores request-callbacks; it never stores any business task
state.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..model.idle_beat import IdleBeatRequest
from ..model.kill import KillRequest
from ..model.log import LogRequest
from ..model.trigger import TriggerRequest
from ..response.executor import XXLJobResponse
from ..response.log import LogResponse

# 处理函数类型别名 / Callback type aliases.
RunCallback = Callable[[TriggerRequest], object]
IdleBeatCallback = Callable[[IdleBeatRequest], object]
KillCallback = Callable[[KillRequest], object]
LogCallback = Callable[[LogRequest], LogResponse]


class CallbackRegistry:
    """
    保存单个 Flask 应用注册的四个 XXL-JOB 请求处理函数。

    每个 Flask 应用拥有独立的注册表实例，从而实现应用间隔离。

    Holds the four XXL-JOB request-callbacks registered for a single Flask
    application. Each Flask application owns an independent registry instance,
    providing per-application isolation.
    """

    def __init__(self) -> None:
        self._run: Optional[RunCallback] = None
        self._idle_beat: Optional[IdleBeatCallback] = None
        self._kill: Optional[KillCallback] = None
        self._log: Optional[LogCallback] = None

    def set_run(self, func: RunCallback) -> RunCallback:
        """注册 ``/run`` 处理函数。 / Register the ``/run`` callback."""
        self._run = func
        return func

    def set_idle_beat(self, func: IdleBeatCallback) -> IdleBeatCallback:
        """注册 ``/idleBeat`` 处理函数。 / Register the ``/idleBeat`` callback."""
        self._idle_beat = func
        return func

    def set_kill(self, func: KillCallback) -> KillCallback:
        """注册 ``/kill`` 处理函数。 / Register the ``/kill`` callback."""
        self._kill = func
        return func

    def set_log(self, func: LogCallback) -> LogCallback:
        """注册 ``/log`` 处理函数。 / Register the ``/log`` callback."""
        self._log = func
        return func

    @property
    def run(self) -> Optional[RunCallback]:
        """已注册的 ``/run`` 处理函数。 / The registered ``/run`` callback."""
        return self._run

    @property
    def idle_beat(self) -> Optional[IdleBeatCallback]:
        """已注册的 ``/idleBeat`` 处理函数。 / The registered ``/idleBeat`` callback."""
        return self._idle_beat

    @property
    def kill(self) -> Optional[KillCallback]:
        """已注册的 ``/kill`` 处理函数。 / The registered ``/kill`` callback."""
        return self._kill

    @property
    def log(self) -> Optional[LogCallback]:
        """已注册的 ``/log`` 处理函数。 / The registered ``/log`` callback."""
        return self._log


__all__ = [
    "CallbackRegistry",
    "RunCallback",
    "IdleBeatCallback",
    "KillCallback",
    "LogCallback",
    "XXLJobResponse",
]

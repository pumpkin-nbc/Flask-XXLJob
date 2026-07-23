"""
保存 Flask 项目注册的 XXL-JOB 请求处理函数。

Stores the XXL-JOB request-callbacks registered by the Flask project.

此模块只保存请求处理函数，不保存任何业务任务状态。

This module only stores request-callbacks; it never stores any business task
state.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Dict, Mapping, Optional

from ..exceptions import XXLJobCallbackRegistrationError
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


def validate_executor_handler(executor_handler: object) -> str:
    """Validate and return an exact XXL-JOB ``executorHandler`` name."""
    if not isinstance(executor_handler, str):
        raise XXLJobCallbackRegistrationError(
            "XXL-JOB executor_handler must be a non-empty string without "
            "leading or trailing whitespace"
        )
    if not executor_handler or executor_handler.strip() != executor_handler:
        raise XXLJobCallbackRegistrationError(
            "XXL-JOB executor_handler must be a non-empty string without "
            "leading or trailing whitespace"
        )
    return executor_handler


def _validate_callback(name: str, func: object) -> None:
    if not callable(func):
        raise XXLJobCallbackRegistrationError(
            f"XXL-JOB {name} callback must be callable"
        )


class CallbackRegistry:
    """
    保存单个 Flask 应用注册的 XXL-JOB 请求处理函数。

    每个 Flask 应用拥有独立的注册表实例，从而实现应用间隔离。

    Holds the named Run callbacks plus the three other request-callbacks for a
    single Flask application. Each application owns an independent registry.
    """

    def __init__(self) -> None:
        self._run: Dict[str, RunCallback] = {}
        self._idle_beat: Optional[IdleBeatCallback] = None
        self._kill: Optional[KillCallback] = None
        self._log: Optional[LogCallback] = None

    def set_run(
        self,
        executor_handler: str,
        func: RunCallback,
        replace: bool = False,
    ) -> RunCallback:
        """注册命名的 ``/run`` 处理函数。 / Register a named ``/run`` callback."""
        self.register_callbacks(run={executor_handler: func}, replace=replace)
        return func

    def set_idle_beat(
        self, func: IdleBeatCallback, replace: bool = False
    ) -> IdleBeatCallback:
        """注册 ``/idleBeat`` 处理函数。 / Register the ``/idleBeat`` callback."""
        self.register_callbacks(idle_beat=func, replace=replace)
        return func

    def set_kill(self, func: KillCallback, replace: bool = False) -> KillCallback:
        """注册 ``/kill`` 处理函数。 / Register the ``/kill`` callback."""
        self.register_callbacks(kill=func, replace=replace)
        return func

    def set_log(self, func: LogCallback, replace: bool = False) -> LogCallback:
        """注册 ``/log`` 处理函数。 / Register the ``/log`` callback."""
        self.register_callbacks(log=func, replace=replace)
        return func

    def register_callbacks(
        self,
        *,
        run: Optional[Mapping[str, RunCallback]] = None,
        idle_beat: Optional[IdleBeatCallback] = None,
        kill: Optional[KillCallback] = None,
        log: Optional[LogCallback] = None,
        replace: bool = False,
    ) -> None:
        """完整验证一批处理函数并一次提交。 / Validate and commit atomically."""
        new_run = dict(self._run)
        new_idle_beat = self._idle_beat
        new_kill = self._kill
        new_log = self._log

        if run is not None:
            if not isinstance(run, Mapping):
                raise XXLJobCallbackRegistrationError(
                    "XXL-JOB run callbacks must be a mapping of "
                    "executor_handler names to callables"
                )
            for executor_handler, func in run.items():
                name = validate_executor_handler(executor_handler)
                _validate_callback(f"run[{name!r}]", func)
                if name in new_run and not replace:
                    raise XXLJobCallbackRegistrationError(
                        f"XXL-JOB run callback for executor_handler {name!r} has "
                        "already been registered; pass replace=True to override it"
                    )
                new_run[name] = func

        self._validate_single("idleBeat", idle_beat, new_idle_beat, replace)
        self._validate_single("kill", kill, new_kill, replace)
        self._validate_single("log", log, new_log, replace)

        if idle_beat is not None:
            new_idle_beat = idle_beat
        if kill is not None:
            new_kill = kill
        if log is not None:
            new_log = log

        self._run = new_run
        self._idle_beat = new_idle_beat
        self._kill = new_kill
        self._log = new_log

    @staticmethod
    def _validate_single(
        name: str,
        func: Optional[Callable[..., object]],
        existing: Optional[Callable[..., object]],
        replace: bool,
    ) -> None:
        if func is None:
            return
        _validate_callback(name, func)
        if existing is not None and not replace:
            raise XXLJobCallbackRegistrationError(
                f"XXL-JOB {name} callback has already been registered; pass "
                "replace=True to override it"
            )

    def seed_from(self, other: "CallbackRegistry") -> None:
        """
        从另一个注册表复制已注册的处理函数（内部使用，不抛异常）。

        ``init_app()`` 用它把扩展级默认处理函数注入到每个应用的注册表中。
        只复制目标尚未设置的处理函数，因此应用级注册可以覆盖默认值而不冲突。

        Copy registered callbacks from another registry (internal use, does not
        raise).

        ``init_app()`` uses this to seed each application's registry with the
        extension-level default callbacks. Only callbacks that are not already
        set on this registry are copied, so application-level registration can
        override the defaults without conflict.
        """
        for executor_handler, func in other._run.items():
            self._run.setdefault(executor_handler, func)
        if self._idle_beat is None:
            self._idle_beat = other._idle_beat
        if self._kill is None:
            self._kill = other._kill
        if self._log is None:
            self._log = other._log

    @property
    def run(self) -> Mapping[str, RunCallback]:
        """已注册的命名 ``/run`` 处理函数只读快照。 / Named callback snapshot."""
        return MappingProxyType(dict(self._run))

    def get_run(self, executor_handler: str) -> Optional[RunCallback]:
        """返回精确 JobHandler 对应的处理函数。 / Return an exact match."""
        return self._run.get(executor_handler)

    @property
    def has_run_callbacks(self) -> bool:
        """是否至少注册了一个命名 Run Handler。 / Whether any are registered."""
        return bool(self._run)

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
    "validate_executor_handler",
    "XXLJobResponse",
]

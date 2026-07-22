"""
Flask-XXLJob 扩展主类。

Flask-XXLJob main extension class.
"""

from __future__ import annotations

import atexit
import os
from typing import TYPE_CHECKING, Any, Optional

from flask import Flask, current_app, has_app_context

from .callback.registry import (
    CallbackRegistry,
    IdleBeatCallback,
    KillCallback,
    LogCallback,
    RunCallback,
)
from .client.admin_client import AdminClient
from .client.callback_client import CallbackClient
from .config import XXLJobConfig
from .exceptions import XXLJobAlreadyInitializedError, XXLJobError, XXLJobRequestError
from .protocol.blueprint import build_blueprint
from .registry.registry_service import RegistryService
from .response.executor import FAIL_CODE, SUCCESS_CODE
from .runtime import XXLJobRuntime

if TYPE_CHECKING:
    from typing import Sequence

    from .client import CallResult
    from .client.callback_client import CallbackLike
    from .status import XXLJobStatus

# Runtime 在 app.extensions 中的键 / Runtime key in app.extensions.
EXTENSION_KEY = "xxljob"


class FlaskXXLJob:
    """
    实现官方 XXL-JOB 2.4.1 执行器协议的 Flask 扩展。

    该扩展只负责协议接入：接收调度请求、校验 Token、解析参数、调用 Flask 项目
    注册的普通处理函数，并提供执行器注册与任务结果回调能力。它不执行任何业务
    任务，也不创建线程池、进程池或任务队列。

    A Flask extension that implements the official XXL-JOB 2.4.1 executor
    protocol.

    The extension only handles protocol integration: receiving scheduler
    requests, validating the token, parsing parameters, dispatching to plain
    request-callbacks registered by the Flask project, and providing executor
    registration and task-result callbacks. It never executes business tasks
    and never creates thread pools, process pools or task queues.
    """

    def __init__(self, app: Optional[Flask] = None) -> None:
        """
        创建扩展实例。传入 ``app`` 时立即初始化，否则延迟到 ``init_app``。

        构造阶段不会访问 ``current_app``。

        Create the extension. When ``app`` is given it is initialized
        immediately; otherwise initialization is deferred to ``init_app``.

        ``current_app`` is never accessed during construction.
        """
        self._app: Optional[Flask] = None
        # 扩展级默认处理函数：在任何 app 初始化前（模块级装饰器）注册的函数暂存
        # 于此，并在 ``init_app()`` 时注入到每个应用的注册表中。
        # Extension-level default callbacks: callbacks registered before any app
        # is initialized (module-level decorators) are buffered here and seeded
        # into every application's registry during ``init_app()``.
        self._deferred_callbacks = CallbackRegistry()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """
        在给定的 Flask 应用上初始化扩展。

        依次读取并校验配置、创建 Runtime 及各客户端、注册 Blueprint 与 CLI、将
        Runtime 保存到 ``app.extensions["xxljob"]``，并按配置决定是否启动自动
        注册。

        Initialize the extension for the given Flask application.

        It reads and validates configuration, creates the runtime and clients,
        registers the blueprint and CLI, stores the runtime in
        ``app.extensions["xxljob"]``, and starts auto-registration when
        configured.
        """
        if not hasattr(app, "extensions"):
            app.extensions = {}

        if EXTENSION_KEY in app.extensions:
            raise XXLJobAlreadyInitializedError(
                "Flask-XXLJob has already been initialized on this application. "
                "Call init_app(app) only once per application."
            )

        config = XXLJobConfig.from_mapping(app.config)

        callback_registry = CallbackRegistry()
        # 将模块级默认处理函数注入到本应用的注册表，支持在 init_app 之前注册。
        # Seed this application's registry with module-level default callbacks,
        # enabling registration before init_app.
        callback_registry.seed_from(self._deferred_callbacks)
        admin_client = AdminClient(config)
        callback_client = CallbackClient(config)
        registry_service = RegistryService(config, admin_client)

        runtime = XXLJobRuntime(
            config=config,
            callback_registry=callback_registry,
            admin_client=admin_client,
            callback_client=callback_client,
            registry_service=registry_service,
        )
        app.extensions[EXTENSION_KEY] = runtime

        if config.enabled:
            blueprint = build_blueprint(_blueprint_name(app), config.route_prefix)
            app.register_blueprint(blueprint)
            self._register_protocol_error_handlers(app, config.route_prefix)

        self._register_cli(app)

        self._app = app

        if config.enabled and config.auto_register and self._should_start_registry(app):
            registry_service.start()
            atexit.register(_safe_stop, registry_service)

    @staticmethod
    def _should_start_registry(app: Flask) -> bool:
        # 避免在 Flask debug reloader 的父进程中重复启动注册线程。
        # Avoid starting the registry thread twice under the Flask debug
        # reloader: only start in the reloader child, or when not reloading.
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            return True
        return not app.debug

    def _register_cli(self, app: Flask) -> None:
        from .cli.commands import xxljob_cli

        # 幂等注册 CLI 分组。 / Register the CLI group idempotently.
        if "xxljob" not in app.cli.commands:
            app.cli.add_command(xxljob_cli)

    @staticmethod
    def _register_protocol_error_handlers(app: Flask, route_prefix: str) -> None:
        # 路由级错误（404/405）在进入 Blueprint 视图前抛出，Blueprint 的 errorhandler
        # 无法捕获。这里在应用级注册处理器，但仅对执行器接口路径返回 XXL-JOB JSON，
        # 其余路径保持 Flask 默认行为，避免影响宿主应用。
        # Routing errors (404/405) are raised before the blueprint view runs, so
        # a blueprint errorhandler cannot catch them. Register app-level handlers
        # that return XXL-JOB JSON only for executor endpoint paths and preserve
        # Flask's default behavior for every other path.
        from flask import jsonify, request
        from werkzeug.exceptions import HTTPException

        from .response.executor import XXLJobResponse

        prefix = route_prefix or ""
        executor_paths = {
            prefix + suffix
            for suffix in ("/beat", "/idleBeat", "/run", "/kill", "/log")
        }

        def _handle(exc: HTTPException) -> Any:
            if request.path in executor_paths:
                return jsonify(
                    XXLJobResponse.failure(
                        "XXL-JOB request error: " + (exc.name or "error")
                    ).to_dict()
                )
            return exc

        app.register_error_handler(404, _handle)
        app.register_error_handler(405, _handle)

    # ------------------------------------------------------------------
    # 请求处理函数注册 / Request-callback registration
    # ------------------------------------------------------------------

    def on_run(self, func: RunCallback) -> RunCallback:
        """
        注册 XXL-JOB ``/run`` 请求处理函数，可作为方法或装饰器使用。

        Register the request callback for the XXL-JOB ``/run`` endpoint. Can be
        used as a method or a decorator.
        """
        return self._target_registry().set_run(func)

    def on_idle_beat(self, func: IdleBeatCallback) -> IdleBeatCallback:
        """
        注册 XXL-JOB ``/idleBeat`` 请求处理函数，可作为方法或装饰器使用。

        Register the request callback for the XXL-JOB ``/idleBeat`` endpoint.
        Can be used as a method or a decorator.
        """
        return self._target_registry().set_idle_beat(func)

    def on_kill(self, func: KillCallback) -> KillCallback:
        """
        注册 XXL-JOB ``/kill`` 请求处理函数，可作为方法或装饰器使用。

        Register the request callback for the XXL-JOB ``/kill`` endpoint. Can
        be used as a method or a decorator.
        """
        return self._target_registry().set_kill(func)

    def on_log(self, func: LogCallback) -> LogCallback:
        """
        注册 XXL-JOB ``/log`` 请求处理函数，可作为方法或装饰器使用。

        Register the request callback for the XXL-JOB ``/log`` endpoint. Can be
        used as a method or a decorator.
        """
        return self._target_registry().set_log(func)

    # ------------------------------------------------------------------
    # 应用级请求处理函数注册 / Application-level callback registration
    # ------------------------------------------------------------------

    def register_callbacks(
        self,
        app: Optional[Flask] = None,
        *,
        run: Optional[RunCallback] = None,
        idle_beat: Optional[IdleBeatCallback] = None,
        kill: Optional[KillCallback] = None,
        log: Optional[LogCallback] = None,
        replace: bool = False,
    ) -> None:
        """
        为指定 Flask 应用一次性注册一个或多个请求处理函数。

        所有处理函数参数均可选。``app`` 为 ``None`` 时使用当前应用上下文或最近一次
        初始化的应用；显式传入 ``app`` 时用于多应用场景。除非 ``replace=True``，
        否则重复注册会抛出 :class:`XXLJobCallbackRegistrationError`。

        Register one or more request-callbacks for a Flask application at once.

        All callback arguments are optional. When ``app`` is ``None`` the current
        application context (or the most recently initialized app) is used;
        passing ``app`` explicitly supports multi-application setups. Duplicate
        registration raises :class:`XXLJobCallbackRegistrationError` unless
        ``replace=True``.
        """
        registry = self._registry_for(app)
        if run is not None:
            registry.set_run(run, replace=replace)
        if idle_beat is not None:
            registry.set_idle_beat(idle_beat, replace=replace)
        if kill is not None:
            registry.set_kill(kill, replace=replace)
        if log is not None:
            registry.set_log(log, replace=replace)

    def set_run_callback(
        self, app: Optional[Flask], func: RunCallback, replace: bool = False
    ) -> RunCallback:
        """为指定应用注册 ``/run`` 处理函数。 / Register the ``/run`` callback for an app."""
        return self._registry_for(app).set_run(func, replace=replace)

    def set_idle_beat_callback(
        self, app: Optional[Flask], func: IdleBeatCallback, replace: bool = False
    ) -> IdleBeatCallback:
        """为指定应用注册 ``/idleBeat`` 处理函数。 / Register the ``/idleBeat`` callback."""
        return self._registry_for(app).set_idle_beat(func, replace=replace)

    def set_kill_callback(
        self, app: Optional[Flask], func: KillCallback, replace: bool = False
    ) -> KillCallback:
        """为指定应用注册 ``/kill`` 处理函数。 / Register the ``/kill`` callback."""
        return self._registry_for(app).set_kill(func, replace=replace)

    def set_log_callback(
        self, app: Optional[Flask], func: LogCallback, replace: bool = False
    ) -> LogCallback:
        """为指定应用注册 ``/log`` 处理函数。 / Register the ``/log`` callback."""
        return self._registry_for(app).set_log(func, replace=replace)

    def get_run_callback(self, app: Optional[Flask] = None) -> Optional[RunCallback]:
        """返回指定应用的 ``/run`` 处理函数。 / Return the app's ``/run`` callback."""
        return self._registry_for(app).run

    def get_idle_beat_callback(
        self, app: Optional[Flask] = None
    ) -> Optional[IdleBeatCallback]:
        """返回指定应用的 ``/idleBeat`` 处理函数。 / Return the app's ``/idleBeat`` callback."""
        return self._registry_for(app).idle_beat

    def get_kill_callback(self, app: Optional[Flask] = None) -> Optional[KillCallback]:
        """返回指定应用的 ``/kill`` 处理函数。 / Return the app's ``/kill`` callback."""
        return self._registry_for(app).kill

    def get_log_callback(self, app: Optional[Flask] = None) -> Optional[LogCallback]:
        """返回指定应用的 ``/log`` 处理函数。 / Return the app's ``/log`` callback."""
        return self._registry_for(app).log

    # ------------------------------------------------------------------
    # 执行器注册 / Executor registration
    # ------------------------------------------------------------------

    def register_executor(self, app: Optional[Flask] = None) -> "CallResult":
        """
        主动向 XXL-JOB Admin 注册执行器。

        Actively register the executor with the XXL-JOB admin.
        """
        return self._get_runtime(app).registry_service.register_once_result()

    def remove_executor(self, app: Optional[Flask] = None) -> "CallResult":
        """
        主动向 XXL-JOB Admin 注销执行器。

        Actively deregister the executor from the XXL-JOB admin.
        """
        return self._get_runtime(app).registry_service.remove_once_result()

    # ------------------------------------------------------------------
    # 任务结果回调 / Task-result callbacks
    # ------------------------------------------------------------------

    def callback(
        self,
        log_id: int,
        log_date_time: int,
        handle_code: int,
        handle_msg: Optional[str] = None,
        app: Optional[Flask] = None,
    ) -> "CallResult":
        """
        向 XXL-JOB Admin 发送任务最终执行结果回调。

        在 Flask 应用上下文中可省略 ``app`` 参数。``handle_msg`` 为 ``None`` 时
        按空信息处理。``log_id`` 与 ``log_date_time`` 必须为整数（不接受布尔值）。

        Send the final task-execution result callback to the XXL-JOB admin.

        The ``app`` argument may be omitted inside a Flask application context.
        A ``None`` ``handle_msg`` is treated as an empty message. ``log_id`` and
        ``log_date_time`` must be integers (booleans are rejected).
        """
        _require_int("log_id", log_id)
        _require_int("log_date_time", log_date_time)
        _require_int("handle_code", handle_code)
        runtime = self._get_runtime(app)
        return runtime.callback_client.callback(
            log_id=log_id,
            log_date_time=log_date_time,
            handle_code=handle_code,
            handle_msg=handle_msg or "",
        )

    def callback_success(
        self,
        log_id: int,
        log_date_time: int,
        message: Optional[str] = None,
        app: Optional[Flask] = None,
    ) -> "CallResult":
        """
        发送任务成功回调（``handle_code=200``）。

        Send a task-success callback (``handle_code=200``).
        """
        return self.callback(
            log_id=log_id,
            log_date_time=log_date_time,
            handle_code=SUCCESS_CODE,
            handle_msg=message,
            app=app,
        )

    def callback_failure(
        self,
        log_id: int,
        log_date_time: int,
        message: Optional[str] = None,
        app: Optional[Flask] = None,
    ) -> "CallResult":
        """
        发送任务失败回调（``handle_code=500``）。

        Send a task-failure callback (``handle_code=500``).
        """
        return self.callback(
            log_id=log_id,
            log_date_time=log_date_time,
            handle_code=FAIL_CODE,
            handle_msg=message,
            app=app,
        )

    def callback_many(
        self,
        callbacks: "Sequence[CallbackLike]",
        app: Optional[Flask] = None,
    ) -> "CallResult":
        """
        在一次官方请求中批量发送多条任务结果回调。

        发送前会完整校验所有条目，超过批量上限或存在非法条目时抛出异常且不发送任何
        数据（全有或全无）。在 Flask 应用上下文中可省略 ``app`` 参数。

        Send multiple task-result callbacks in a single official request.

        All items are validated before sending; exceeding the batch limit or an
        invalid item raises without sending any data (all-or-nothing). The
        ``app`` argument may be omitted inside a Flask application context.
        """
        return self._get_runtime(app).callback_client.callback_many(callbacks)

    # ------------------------------------------------------------------
    # 插件状态与注册生命周期 / Plugin status and registry lifecycle
    # ------------------------------------------------------------------

    def get_status(self, app: Optional[Flask] = None) -> "XXLJobStatus":
        """
        返回插件运行状态快照（是否启用、是否自动注册、最近一次注册结果等）。

        该状态只描述 Flask-XXLJob 插件自身，绝不包含 Access Token 或业务任务状态。

        Return a snapshot of the plugin runtime status (enabled, auto-register,
        last registration result, and so on).

        The status only describes the Flask-XXLJob plugin itself; it never
        contains the access token or any business-task state.
        """
        from .status import XXLJobStatus

        runtime = self._get_runtime(app)
        config = runtime.config
        snapshot = runtime.registry_service.status_snapshot()
        return XXLJobStatus(
            enabled=config.enabled,
            auto_register=config.auto_register,
            registered=snapshot["registered"],
            last_registry_time=snapshot["last_registry_time"],
            last_registry_success=snapshot["last_registry_success"],
            last_registry_admin_address=snapshot["last_registry_admin_address"],
            last_registry_error_type=snapshot["last_registry_error_type"],
            last_registry_message=snapshot["last_registry_message"],
            registry_thread_running=snapshot["registry_thread_running"],
        )

    def start_registry(self, app: Optional[Flask] = None) -> None:
        """
        启动执行器自动注册/续约线程（幂等）。

        Start the executor auto-registration/renewal thread (idempotent).
        """
        self._get_runtime(app).registry_service.start()

    def stop_registry(self, app: Optional[Flask] = None) -> None:
        """
        停止执行器自动注册/续约线程并注销执行器。

        Stop the executor auto-registration/renewal thread and deregister.
        """
        self._get_runtime(app).registry_service.stop()

    # ------------------------------------------------------------------
    # 内部辅助 / Internal helpers
    # ------------------------------------------------------------------

    def _get_runtime(self, app: Optional[Flask] = None) -> XXLJobRuntime:
        target = self._resolve_app(app)
        try:
            return target.extensions[EXTENSION_KEY]
        except (AttributeError, KeyError) as exc:
            raise XXLJobError(
                "Flask-XXLJob is not initialized on this application. "
                "Call init_app(app) first."
            ) from exc

    def _resolve_app(self, app: Optional[Flask]) -> Flask:
        if app is not None:
            return app
        # 使用 has_app_context() 而不是布尔判断 current_app，避免上下文外抛出
        # 难以理解的 RuntimeError。
        # Use has_app_context() rather than truth-testing current_app to avoid a
        # confusing RuntimeError when there is no application context.
        if has_app_context():
            return current_app._get_current_object()  # type: ignore[attr-defined]
        if self._app is not None:
            return self._app
        raise XXLJobError(
            "No Flask application available. Pass app=... or run within an "
            "application context."
        )

    def _target_registry(self) -> CallbackRegistry:
        # 处理函数注册目标解析：
        # 1. 应用上下文内 -> 当前应用注册表；
        # 2. 已初始化过应用 -> 最近一次初始化的应用注册表；
        # 3. 尚未初始化 -> 扩展级默认注册表（延迟注入）。
        # Resolve the registration target:
        # 1. within an app context -> current application's registry;
        # 2. an app was initialized -> the most recently initialized app's;
        # 3. no app yet -> the extension-level deferred registry.
        if has_app_context():
            return self._get_runtime().callback_registry
        if self._app is not None:
            return self._get_runtime(self._app).callback_registry
        return self._deferred_callbacks

    def _registry_for(self, app: Optional[Flask]) -> CallbackRegistry:
        # 显式传入 app -> 使用该应用的注册表（要求已初始化）；
        # 未传入 -> 与装饰器一致，使用上下文/最近应用/延迟注册表。
        # Explicit app -> that application's registry (must be initialized);
        # omitted -> same as decorators: context / last-app / deferred registry.
        if app is not None:
            return self._get_runtime(app).callback_registry
        return self._target_registry()


def _require_int(name: str, value: object) -> None:
    # bool 是 int 的子类，但回调参数不接受布尔值。
    # bool is a subclass of int, but callback arguments reject booleans.
    if isinstance(value, bool) or not isinstance(value, int):
        raise XXLJobRequestError(
            f"{name} must be an integer, got {type(value).__name__}"
        )


def _blueprint_name(app: Flask) -> str:
    # 每个应用使用带应用名的唯一 Blueprint 名称。
    # Use a unique blueprint name that includes the application name.
    return "xxljob_" + app.name.replace(".", "_")


def _safe_stop(registry_service: RegistryService) -> None:
    try:
        registry_service.stop()
    except Exception:  # noqa: BLE001 - 关闭阶段静默 / stay quiet during shutdown
        pass


__all__ = ["FlaskXXLJob", "EXTENSION_KEY"]

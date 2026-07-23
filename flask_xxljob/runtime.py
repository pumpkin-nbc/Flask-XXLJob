"""
Flask-XXLJob 运行时对象。

Flask-XXLJob runtime object.

Runtime 只保存协议接入所需组件，不保存任何业务任务相关内容（执行器适配器、
线程池、进程池、业务 Handler、任务队列、任务状态、业务日志、数据库/Redis/
Celery 连接等一律不保存）。

The runtime only holds protocol-integration components. It never stores any
business-task related objects (no executor adapter, thread pool, process pool,
business handler, task queue, task state, business logs, or database/Redis/
Celery connections).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING
from weakref import finalize

if TYPE_CHECKING:
    from ._logging import XXLJobLogManager
    from .callback.registry import CallbackRegistry
    from .client.admin_client import AdminClient
    from .client.callback_client import CallbackClient
    from .config import XXLJobConfig
    from .registry.registry_service import RegistryService


class XXLJobRuntime:
    """
    单个 Flask 应用的 Flask-XXLJob 运行时，保存在
    ``app.extensions["xxljob"]``。

    The per-application Flask-XXLJob runtime, stored in
    ``app.extensions["xxljob"]``.
    """

    def __init__(
        self,
        config: "XXLJobConfig",
        callback_registry: "CallbackRegistry",
        admin_client: "AdminClient",
        callback_client: "CallbackClient",
        registry_service: "RegistryService",
        log_manager: "XXLJobLogManager",
    ) -> None:
        self.config = config
        self.callback_registry = callback_registry
        self.admin_client = admin_client
        self.callback_client = callback_client
        self.registry_service = registry_service
        self.log_manager = log_manager
        self._close_lock = threading.Lock()
        self._closed = False
        self._finalizer: "finalize | None" = None

    def attach_finalizer(self, finalizer: "finalize") -> None:
        self._finalizer = finalizer

    def close(self) -> None:
        """Best-effort, idempotent internal runtime cleanup."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True

        self.log_manager.prepare_shutdown()
        logger = self.log_manager.get_logger("runtime")
        logger.info("Flask-XXLJob runtime shutdown started.")
        snapshot = self.registry_service.status_snapshot()
        remove = bool(
            self.config.enabled
            and (
                snapshot["registered"]
                or snapshot["registry_thread_running"]
            )
        )
        try:
            self.registry_service.stop(
                remove=remove,
                on_stopped=self._finish_close,
            )
        except Exception as exc:  # noqa: BLE001 - shutdown remains best effort
            logger.error(
                "Flask-XXLJob runtime shutdown failed exception_type=%s.",
                type(exc).__name__,
            )
            self._finish_close()

    def _finish_close(self) -> None:
        logger = self.log_manager.get_logger("runtime")
        logger.info("Flask-XXLJob runtime shutdown completed.")
        self.log_manager.close()

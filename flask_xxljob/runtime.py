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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    ) -> None:
        self.config = config
        self.callback_registry = callback_registry
        self.admin_client = admin_client
        self.callback_client = callback_client
        self.registry_service = registry_service

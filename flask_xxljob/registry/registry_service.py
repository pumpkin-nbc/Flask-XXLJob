"""
执行器注册与自动续约服务。

Executor registration and auto-renewal service.

该服务只负责执行器注册续约，不处理任何业务任务。注册线程为守护线程，注册失败
不会影响 Flask 主应用启动。

This service only handles executor registration and renewal; it never handles
any business task. The renewal thread is a daemon thread, and registration
failures never prevent the Flask application from starting.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from ..client import CallResult
from ..client.admin_client import AdminClient
from ..config import XXLJobConfig
from ..model.registry import RegistryRequest

logger = logging.getLogger("flask_xxljob.registry")


class RegistryService:
    """
    管理执行器的注册、定时续约与注销。

    Manages executor registration, periodic renewal and deregistration.
    """

    def __init__(self, config: XXLJobConfig, admin_client: AdminClient) -> None:
        self._config = config
        self._admin_client = admin_client
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def _build_request(self) -> RegistryRequest:
        return RegistryRequest.for_executor(
            app_name=self._config.executor_app_name,
            address=self._config.executor_address,
        )

    def register_once_result(self) -> CallResult:
        """
        执行一次注册/续约调用并返回完整结果。

        Perform a single registration/renewal call and return the full result.
        """
        result = self._admin_client.registry(self._build_request())
        if result.success:
            logger.info(
                "XXL-JOB executor registered via %s (app=%s).",
                result.address,
                self._config.executor_app_name,
            )
        else:
            logger.warning(
                "XXL-JOB executor registration failed: %s",
                result.error or result.msg,
            )
        return result

    def remove_once_result(self) -> CallResult:
        """
        执行一次注销调用并返回完整结果。

        Perform a single deregistration call and return the full result.
        """
        result = self._admin_client.registry_remove(self._build_request())
        if result.success:
            logger.info("XXL-JOB executor removed via %s.", result.address)
        else:
            logger.warning(
                "XXL-JOB executor removal failed: %s",
                result.error or result.msg,
            )
        return result

    def register_once(self) -> bool:
        """
        执行一次注册/续约调用。返回是否成功。

        Perform a single registration/renewal call. Returns whether it
        succeeded.
        """
        result = self._admin_client.registry(self._build_request())
        if result.success:
            logger.info(
                "XXL-JOB executor registered via %s (app=%s).",
                result.address,
                self._config.executor_app_name,
            )
        else:
            logger.warning(
                "XXL-JOB executor registration failed: %s",
                result.error or result.msg,
            )
        return result.success

    def remove_once(self) -> bool:
        """
        执行一次注销调用。返回是否成功。

        Perform a single deregistration call. Returns whether it succeeded.
        """
        result = self._admin_client.registry_remove(self._build_request())
        if result.success:
            logger.info("XXL-JOB executor removed via %s.", result.address)
        else:
            logger.warning(
                "XXL-JOB executor removal failed: %s",
                result.error or result.msg,
            )
        return result.success

    def start(self) -> None:
        """
        启动后台续约线程。重复调用具有幂等性。

        注册失败不会抛出异常，也不会影响 Flask 应用启动。

        Start the background renewal thread. Repeated calls are idempotent.

        Registration failures never raise and never affect application
        startup.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            thread = threading.Thread(
                target=self._run_loop,
                name="flask-xxljob-registry",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def _run_loop(self) -> None:
        interval = self._config.registry_interval
        # 立即注册一次，随后按间隔续约。
        # Register immediately, then renew on the configured interval.
        try:
            self.register_once()
        except Exception:  # noqa: BLE001 - 保护主流程 / protect the main flow
            logger.exception("Unexpected error during XXL-JOB registration.")
        while not self._stop_event.wait(interval):
            try:
                self.register_once()
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error during XXL-JOB registration renewal.")

    def stop(self, remove: bool = True) -> None:
        """
        停止续约线程，可选地注销执行器。

        Stop the renewal thread and optionally deregister the executor.
        """
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=self._config.registry_interval)
        self._thread = None
        if remove:
            try:
                self.remove_once()
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error during XXL-JOB executor removal.")

    @property
    def is_running(self) -> bool:
        """续约线程是否正在运行。 / Whether the renewal thread is running."""
        return self._thread is not None and self._thread.is_alive()

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
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .._logging import redact_text
from ..client import CallResult
from ..client.admin_client import AdminClient
from ..config import XXLJobConfig
from ..model.registry import RegistryRequest


class RegistryService:
    """
    管理执行器的注册、定时续约与注销。

    Manages executor registration, periodic renewal and deregistration.
    """

    def __init__(
        self,
        config: XXLJobConfig,
        admin_client: AdminClient,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._config = config
        self._admin_client = admin_client
        self._logger = logger or logging.getLogger("flask_xxljob.registry")
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # 生命周期锁串行化 start/stop；调用锁串行化注册与注销请求。
        # The lifecycle lock serializes start/stop; the call lock serializes
        # registration and deregistration requests.
        self._lock = threading.Lock()
        self._call_lock = threading.Lock()
        # A stop request may time out while a renewal call is still in flight.
        # Keep the deregistration intent until the worker exits, and let exactly
        # one caller claim it.  These flags are protected by ``_lock``.
        self._remove_requested = False
        self._remove_claimed = False
        self._shutdown_callbacks: List[Callable[[], None]] = []
        # 最近一次注册/续约/注销结果（仅插件状态，绝不含 Token 或业务状态）。
        # Last registration/renewal/removal result (plugin status only; never a
        # token or any business state).
        self._status_lock = threading.Lock()
        self._registered = False
        self._last_registry_time: Optional[str] = None
        self._last_registry_success: Optional[bool] = None
        self._last_registry_admin_address: Optional[str] = None
        self._last_registry_error_type: Optional[str] = None
        self._last_registry_message: Optional[str] = None

    def _record(self, result: CallResult, *, is_remove: bool) -> None:
        # 记录最近一次调用的插件级状态，供 get_status 查询。
        # Record plugin-level status of the latest call for get_status.
        with self._status_lock:
            self._last_registry_time = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            self._last_registry_success = result.success
            self._last_registry_admin_address = result.address
            self._last_registry_error_type = result.error_type
            self._last_registry_message = (
                redact_text(result.message, self._config.access_token)
                if result.message is not None
                else None
            )
            if result.success:
                # 注册成功 -> 已注册；注销成功 -> 未注册。
                # Successful register -> registered; successful remove -> not.
                self._registered = not is_remove

    def status_snapshot(self) -> Dict[str, Any]:
        """
        返回最近一次注册状态的快照（不含 Token 或业务状态）。

        Return a snapshot of the latest registration status (never a token or
        any business state).
        """
        with self._status_lock:
            return {
                "registered": self._registered,
                "last_registry_time": self._last_registry_time,
                "last_registry_success": self._last_registry_success,
                "last_registry_admin_address": self._last_registry_admin_address,
                "last_registry_error_type": self._last_registry_error_type,
                "last_registry_message": self._last_registry_message,
                "registry_thread_running": self.is_running,
            }

    def _build_request(self) -> RegistryRequest:
        return RegistryRequest.for_executor(
            app_name=self._config.executor_app_name,
            address=self._config.executor_address,
        )

    def register_once_result(self, *, operation: str = "registration") -> CallResult:
        """
        执行一次注册/续约调用并返回完整结果。

        Perform a single registration/renewal call and return the full result.
        """
        with self._call_lock:
            result = self._admin_client.registry(self._build_request())
            self._record(result, is_remove=False)
            if result.success:
                self._logger.info(
                    "XXL-JOB executor %s succeeded via %s (app=%s).",
                    operation,
                    result.address,
                    self._config.executor_app_name,
                )
            else:
                self._logger.warning(
                    "XXL-JOB executor %s failed error_type=%s http_status=%s.",
                    operation,
                    result.error_type,
                    result.http_status,
                )
            return result

    def remove_once_result(self) -> CallResult:
        """
        执行一次注销调用并返回完整结果。

        Perform a single deregistration call and return the full result.
        """
        with self._call_lock:
            result = self._admin_client.registry_remove(self._build_request())
            self._record(result, is_remove=True)
            if result.success:
                self._logger.info(
                    "XXL-JOB executor removal succeeded via %s.", result.address
                )
            else:
                self._logger.warning(
                    "XXL-JOB executor removal failed error_type=%s "
                    "http_status=%s.",
                    result.error_type,
                    result.http_status,
                )
            return result

    def register_once(self) -> bool:
        """
        执行一次注册/续约调用。返回是否成功。

        Perform a single registration/renewal call. Returns whether it
        succeeded.
        """
        return self.register_once_result().success

    def remove_once(self) -> bool:
        """
        执行一次注销调用。返回是否成功。

        Perform a single deregistration call. Returns whether it succeeded.
        """
        return self.remove_once_result().success

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
            self._remove_requested = False
            self._remove_claimed = False
            thread = threading.Thread(
                target=self._run_loop,
                name="flask-xxljob-registry",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            self._logger.info("XXL-JOB registry renewal thread started.")

    def _run_loop(self) -> None:
        interval = self._config.registry_interval
        try:
            # Register immediately, then renew on the configured interval.
            try:
                self.register_once_result(operation="registration")
            except Exception as exc:  # noqa: BLE001 - protect the main flow
                self._logger.error(
                    "Unexpected error during XXL-JOB registration "
                    "exception_type=%s.",
                    type(exc).__name__,
                )
            while not self._stop_event.wait(interval):
                try:
                    self.register_once_result(operation="renewal")
                except Exception as exc:  # noqa: BLE001
                    self._logger.error(
                        "Unexpected error during XXL-JOB registration renewal "
                        "exception_type=%s.",
                        type(exc).__name__,
                    )
        finally:
            # If stop() could not wait for an in-flight renewal, the worker is
            # responsible for deregistering after that renewal has completed.
            should_remove = self._claim_remove()
            if should_remove:
                self._perform_claimed_remove()
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None
            self._logger.info("XXL-JOB registry renewal thread stopped.")
            self._finish_shutdown()

    def _claim_remove(self) -> bool:
        """Claim a pending deregistration request exactly once."""
        with self._lock:
            if not self._remove_requested or self._remove_claimed:
                return False
            self._remove_claimed = True
            return True

    def _perform_claimed_remove(self) -> None:
        """Perform an already claimed deregistration and record exceptions."""
        try:
            self.remove_once()
        except Exception as exc:  # noqa: BLE001
            self._record(
                CallResult(
                    success=False,
                    error="Unexpected error during XXL-JOB executor removal.",
                    error_type=type(exc).__name__,
                ),
                is_remove=True,
            )
            self._logger.error(
                "Unexpected error during XXL-JOB executor removal "
                "exception_type=%s.",
                type(exc).__name__,
            )

    def stop(
        self,
        remove: bool = True,
        on_stopped: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        停止续约线程，可选地注销执行器。

        Stop the renewal thread and optionally deregister the executor.
        """
        # Record the stop intent while holding the lifecycle lock, but never
        # wait for the worker while holding it: the worker needs the same lock
        # to claim a deferred deregistration request as it exits.
        with self._lock:
            if on_stopped is not None and on_stopped not in self._shutdown_callbacks:
                self._shutdown_callbacks.append(on_stopped)
            self._stop_event.set()
            if remove:
                self._remove_requested = True
            thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=self._config.registry_interval)

        if thread is not None and thread.is_alive():
            # The worker retains the pending remove request and performs it as
            # soon as the in-flight renewal returns.
            self._logger.warning(
                "XXL-JOB registry thread is still stopping after %s seconds; "
                "deregistration will run after the in-flight renewal finishes.",
                self._config.registry_interval,
            )
            return

        with self._lock:
            if self._thread is thread:
                self._thread = None

        if self._claim_remove():
            self._perform_claimed_remove()
        self._logger.info("XXL-JOB registry service stopped.")
        self._finish_shutdown()

    def _finish_shutdown(self) -> None:
        with self._lock:
            callbacks = tuple(self._shutdown_callbacks)
            self._shutdown_callbacks.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    "XXL-JOB runtime cleanup failed exception_type=%s.",
                    type(exc).__name__,
                )

    @property
    def is_running(self) -> bool:
        """续约线程是否正在运行。 / Whether the renewal thread is running."""
        return self._thread is not None and self._thread.is_alive()

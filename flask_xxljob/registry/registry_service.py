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
from typing import Any, Dict, Optional

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
            self._last_registry_message = result.message
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

    def register_once_result(self) -> CallResult:
        """
        执行一次注册/续约调用并返回完整结果。

        Perform a single registration/renewal call and return the full result.
        """
        with self._call_lock:
            result = self._admin_client.registry(self._build_request())
            self._record(result, is_remove=False)
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
        with self._call_lock:
            result = self._admin_client.registry_remove(self._build_request())
            self._record(result, is_remove=True)
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

    def _run_loop(self) -> None:
        interval = self._config.registry_interval
        try:
            # Register immediately, then renew on the configured interval.
            try:
                self.register_once()
            except Exception:  # noqa: BLE001 - protect the main flow
                logger.exception("Unexpected error during XXL-JOB registration.")
            while not self._stop_event.wait(interval):
                try:
                    self.register_once()
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Unexpected error during XXL-JOB registration renewal."
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
            logger.exception("Unexpected error during XXL-JOB executor removal.")

    def stop(self, remove: bool = True) -> None:
        """
        停止续约线程，可选地注销执行器。

        Stop the renewal thread and optionally deregister the executor.
        """
        # Record the stop intent while holding the lifecycle lock, but never
        # wait for the worker while holding it: the worker needs the same lock
        # to claim a deferred deregistration request as it exits.
        with self._lock:
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
            logger.warning(
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

    @property
    def is_running(self) -> bool:
        """续约线程是否正在运行。 / Whether the renewal thread is running."""
        return self._thread is not None and self._thread.is_alive()

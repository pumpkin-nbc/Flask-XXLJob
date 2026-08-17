"""Process-local executor Registry lifecycle management."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set

from .._logging import redact_text
from ..client import CallResult
from ..client.admin_client import AdminClient
from ..config import XXLJobConfig
from ..model.registry import RegistryRequest


@dataclass(eq=False)
class _RegistryWorkerContext:
    """One successfully started Registry renewal lifecycle."""

    generation: int
    stop_event: threading.Event
    thread: Optional[threading.Thread] = None
    wait_remove_event: Optional[threading.Event] = None


@dataclass(eq=False)
class _RemoveOperation:
    """One accepted, at-most-once automatic Registry removal."""

    generation: int
    done_event: threading.Event
    thread: Optional[threading.Thread] = None


@dataclass(eq=False)
class _RegistryProcessState:
    """All Registry state that must be replaced at a PID boundary."""

    pid: int
    state_lock: threading.RLock = field(default_factory=threading.RLock)
    network_lock: threading.Lock = field(default_factory=threading.Lock)
    generation: int = 0
    last_remove_requested_generation: Optional[int] = None
    worker: Optional[_RegistryWorkerContext] = None
    stopping_workers: Dict[int, _RegistryWorkerContext] = field(
        default_factory=dict
    )
    pending_remove: Optional[_RemoveOperation] = None
    active_remove: Optional[_RemoveOperation] = None
    registered: bool = False
    # ``rpc_sequence`` is owned by ``network_lock``.  It is intentionally not
    # read or written while merely holding ``state_lock``.
    rpc_sequence: int = 0
    # ``last_applied_rpc_sequence`` and all snapshots are owned by state_lock.
    last_applied_rpc_sequence: int = 0
    last_result: Optional[CallResult] = None
    last_error: Optional[CallResult] = None
    last_registry_time: Optional[str] = None
    last_registry_success: Optional[bool] = None
    last_registry_admin_address: Optional[str] = None
    last_registry_error_type: Optional[str] = None
    last_registry_message: Optional[str] = None
    cleanup_actors: Set[threading.Thread] = field(default_factory=set)
    close_logs_when_idle: bool = False
    logs_closed: bool = False


class RegistryService:
    """Manage one process's Registry lifecycle and one-shot Registry RPCs."""

    _DISABLED_ERROR = "Flask-XXLJob is disabled."

    def __init__(
        self,
        config: XXLJobConfig,
        admin_client: AdminClient,
        logger: Optional[logging.Logger] = None,
        close_logs: Optional[Callable[[], None]] = None,
    ) -> None:
        self._config = config
        self._admin_client = admin_client
        self._logger = logger or logging.getLogger("flask_xxljob.registry")
        self._close_logs = close_logs
        self._process_state = self._new_process_state(os.getpid())

    @staticmethod
    def _new_process_state(pid: int) -> _RegistryProcessState:
        return _RegistryProcessState(pid=pid)

    def _get_process_state(self) -> _RegistryProcessState:
        """Return a blank current-PID state without touching inherited locks."""
        current_pid = os.getpid()
        state = self._process_state
        if state.pid == current_pid:
            return state

        # At a fork boundary no inherited Lock, Thread or Event may be read or
        # operated on.  Comparing the immutable PID is the only old-state read.
        state = self._new_process_state(current_pid)
        self._process_state = state
        return state

    def _state_is_current(self, state: _RegistryProcessState) -> bool:
        return self._get_process_state() is state

    @staticmethod
    def _is_current_worker(
        state: _RegistryProcessState, ctx: _RegistryWorkerContext
    ) -> bool:
        return state.worker is ctx and state.generation == ctx.generation

    def _safe_result(self, result: CallResult) -> CallResult:
        """Copy a result into the redacted process-local status model."""
        token = self._config.access_token
        return CallResult(
            success=result.success,
            code=result.code,
            msg=(
                redact_text(result.msg, token)
                if result.msg is not None
                else None
            ),
            address=result.address,
            error=(
                redact_text(result.error, token)
                if result.error is not None
                else None
            ),
            error_type=result.error_type,
            attempt_count=result.attempt_count,
            elapsed_ms=result.elapsed_ms,
            http_status=result.http_status,
        )

    def _record_result_locked(
        self,
        state: _RegistryProcessState,
        result: CallResult,
        *,
        operation: str,
    ) -> None:
        """Record one accepted RPC or local failure while holding state_lock."""
        safe = self._safe_result(result)
        state.last_result = safe
        state.last_error = None if safe.success else safe
        state.last_registry_time = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        state.last_registry_success = safe.success
        state.last_registry_admin_address = safe.address
        state.last_registry_error_type = safe.error_type
        state.last_registry_message = safe.message

        if operation == "worker":
            # An accepted renewal failure is the latest knowledge about the
            # current lifecycle and therefore clears the registered snapshot.
            state.registered = safe.success
        elif safe.success and operation == "register":
            state.registered = True
        elif safe.success and operation == "remove":
            state.registered = False
        # One-shot failures, Remove failures, and local disabled/config
        # failures preserve the existing registered snapshot.

    @staticmethod
    def _unexpected_result(action: str, exc: Exception) -> CallResult:
        return CallResult(
            success=False,
            error="Unexpected error during XXL-JOB executor {}.".format(action),
            error_type=type(exc).__name__,
        )

    def _record_local_failure(
        self, state: _RegistryProcessState, result: CallResult
    ) -> None:
        if not self._state_is_current(state):
            return
        with state.state_lock:
            self._record_result_locked(state, result, operation="local")

    def _disabled_result(self) -> CallResult:
        return CallResult(
            success=False,
            error=self._DISABLED_ERROR,
            error_type="config",
            attempt_count=0,
        )

    def _build_request(self) -> RegistryRequest:
        return RegistryRequest.for_executor(
            app_name=self._config.executor_app_name,
            address=self._config.executor_address,
        )

    # ------------------------------------------------------------------
    # Synchronous one-shot Registry API
    # ------------------------------------------------------------------

    def register_once_result(
        self, *, operation: str = "registration"
    ) -> CallResult:
        """Perform one synchronous executor registration RPC."""
        if not self._config.enabled:
            result = self._disabled_result()
            state = self._get_process_state()
            self._record_local_failure(state, result)
            return result

        self._config.validate_registry()
        state = self._get_process_state()
        result, sequence = self._call_registry(state, remove=False)
        self._commit_one_shot(state, result, sequence, remove=False)
        self._log_rpc_result(result, operation)
        return result

    def remove_once_result(self) -> CallResult:
        """Perform one synchronous executor removal RPC."""
        if not self._config.enabled:
            result = self._disabled_result()
            state = self._get_process_state()
            self._record_local_failure(state, result)
            return result

        self._config.validate_registry()
        state = self._get_process_state()
        result, sequence = self._call_registry(state, remove=True)
        self._commit_one_shot(state, result, sequence, remove=True)
        self._log_rpc_result(result, "removal")
        return result

    def _call_registry(
        self, state: _RegistryProcessState, *, remove: bool
    ) -> tuple:
        """Execute a real RPC and allocate its sequence under network_lock."""
        if not self._state_is_current(state):
            # PID cannot normally change inside a call.  This defensive result
            # must not be submitted into either the old or replacement state.
            return (
                CallResult(
                    success=False,
                    error="Registry process state changed before the Admin call.",
                    error_type="process",
                ),
                0,
            )

        with state.network_lock:
            state.rpc_sequence += 1
            sequence = state.rpc_sequence
            try:
                if remove:
                    result = self._admin_client.registry_remove(
                        self._build_request()
                    )
                else:
                    result = self._admin_client.registry(self._build_request())
            except Exception as exc:  # noqa: BLE001 - expose a safe CallResult
                action = "removal" if remove else "registration"
                result = self._unexpected_result(action, exc)
        return result, sequence

    def _commit_one_shot(
        self,
        state: _RegistryProcessState,
        result: CallResult,
        sequence: int,
        *,
        remove: bool,
    ) -> None:
        if sequence == 0 or not self._state_is_current(state):
            return
        with state.state_lock:
            if sequence <= state.last_applied_rpc_sequence:
                return
            self._record_result_locked(
                state,
                result,
                operation="remove" if remove else "register",
            )
            # Accepted failures carry the same ordering significance as
            # accepted successes.
            state.last_applied_rpc_sequence = sequence

    def register_once(self) -> bool:
        return self.register_once_result().success

    def remove_once(self) -> bool:
        return self.remove_once_result().success

    # ------------------------------------------------------------------
    # Renewal lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start one current renewal lifecycle and return without networking."""
        if not self._config.enabled:
            return
        self._config.validate_registry()
        state = self._get_process_state()
        cancelled: Optional[_RemoveOperation] = None

        with state.state_lock:
            existing = state.worker
            if existing is not None:
                if self._is_current_worker(state, existing):
                    return
                # Defensive repair of an internally inconsistent ownership
                # record.  Normal lifecycle transitions never enter here.
                state.worker = None
                state.stopping_workers[existing.generation] = existing
                existing.stop_event.set()

            candidate_generation = state.generation + 1
            ctx = _RegistryWorkerContext(
                generation=candidate_generation,
                stop_event=threading.Event(),
            )
            thread = threading.Thread(
                target=self._run_worker,
                args=(state, ctx),
                name="flask-xxljob-registry",
                daemon=True,
            )
            ctx.thread = thread

            # The worker's first action is to acquire this same state_lock, so
            # it cannot perform a Registry RPC before ownership is committed.
            thread.start()
            state.generation = candidate_generation
            state.worker = ctx

            # Pending and Active may coexist.  These are intentionally two
            # independent branches, not an if/elif pair.
            if state.pending_remove is not None:
                cancelled = state.pending_remove
                state.pending_remove = None
            if state.active_remove is not None:
                ctx.wait_remove_event = state.active_remove.done_event

        if cancelled is not None:
            cancelled.done_event.set()
        self._logger.info(
            "XXL-JOB registry lifecycle started generation=%s.",
            candidate_generation,
        )

    def _run_worker(
        self,
        state: _RegistryProcessState,
        ctx: _RegistryWorkerContext,
    ) -> None:
        try:
            if not self._worker_is_current(state, ctx):
                return

            wait_remove_event = ctx.wait_remove_event
            if wait_remove_event is not None:
                wait_remove_event.wait()
                # An intervening stop may have invalidated this lifecycle while
                # it waited for an older Active Remove.
                if not self._worker_is_current(state, ctx):
                    return

            while self._worker_is_current(state, ctx):
                if not self._perform_worker_registry(state, ctx):
                    return
                if ctx.stop_event.wait(self._config.registry_interval):
                    return
                if not self._worker_is_current(state, ctx):
                    return
        finally:
            self._finish_worker(state, ctx)

    def _worker_is_current(
        self,
        state: _RegistryProcessState,
        ctx: _RegistryWorkerContext,
    ) -> bool:
        # The PID guard must run before even reading an inherited Event.
        if not self._state_is_current(state):
            return False
        if ctx.stop_event.is_set():
            return False
        with state.state_lock:
            return (
                not ctx.stop_event.is_set()
                and self._is_current_worker(state, ctx)
            )

    def _perform_worker_registry(
        self,
        state: _RegistryProcessState,
        ctx: _RegistryWorkerContext,
    ) -> bool:
        if not self._worker_is_current(state, ctx):
            return False

        with state.network_lock:
            if not self._state_is_current(state):
                return False
            # Recheck after waiting for the process-wide network lock.  The
            # temporary state lock below is released before the Admin RPC, so
            # no state lock is held across network I/O.
            with state.state_lock:
                if (
                    ctx.stop_event.is_set()
                    or not self._is_current_worker(state, ctx)
                ):
                    return False
            state.rpc_sequence += 1
            sequence = state.rpc_sequence
            try:
                result = self._admin_client.registry(self._build_request())
            except Exception as exc:  # noqa: BLE001 - worker must keep retrying
                result = self._unexpected_result("registration", exc)

        accepted = False
        still_current = False
        if self._state_is_current(state):
            with state.state_lock:
                still_current = (
                    not ctx.stop_event.is_set()
                    and self._is_current_worker(state, ctx)
                )
                if (
                    still_current
                    and sequence > state.last_applied_rpc_sequence
                ):
                    self._record_result_locked(
                        state, result, operation="worker"
                    )
                    state.last_applied_rpc_sequence = sequence
                    accepted = True

        if accepted:
            self._log_rpc_result(result, "registration renewal")
        return still_current

    def stop(self, remove: bool = False) -> None:
        """Stop locally and optionally enqueue one lifecycle Remove."""
        if not self._config.enabled:
            return
        if remove:
            # Public callers receive deterministic configuration failures
            # before any local stop or background scheduling takes place.
            self._config.validate_registry()

        state = self._get_process_state()
        operation: Optional[_RemoveOperation] = None
        with state.state_lock:
            self._stop_local_locked(state)
            if remove:
                operation = self._request_remove_locked(state)

        if operation is not None:
            self._schedule_pending_remove(state, raise_start_error=True)
        self._maybe_close_logs_when_idle(state)

    @staticmethod
    def _stop_local_locked(state: _RegistryProcessState) -> None:
        ctx = state.worker
        if ctx is None:
            return
        state.worker = None
        state.stopping_workers[ctx.generation] = ctx
        ctx.stop_event.set()

    @staticmethod
    def _request_remove_locked(
        state: _RegistryProcessState,
    ) -> Optional[_RemoveOperation]:
        generation = state.generation
        if generation == 0:
            return None
        if state.last_remove_requested_generation == generation:
            return None
        state.last_remove_requested_generation = generation
        operation = _RemoveOperation(
            generation=generation,
            done_event=threading.Event(),
        )
        state.pending_remove = operation
        return operation

    def _finish_worker(
        self,
        state: _RegistryProcessState,
        ctx: _RegistryWorkerContext,
    ) -> None:
        if not self._state_is_current(state):
            return

        claimed: Optional[_RemoveOperation] = None
        with state.state_lock:
            pending = state.pending_remove
            # The final same-generation claim check and removal from
            # stopping_workers are one atomic critical section.
            if (
                pending is not None
                and pending.generation == ctx.generation
                and state.active_remove is None
            ):
                state.pending_remove = None
                state.active_remove = pending
                claimed = pending

            if state.stopping_workers.get(ctx.generation) is ctx:
                del state.stopping_workers[ctx.generation]
            if state.worker is ctx:
                state.worker = None

        self._logger.info(
            "XXL-JOB registry lifecycle stopped generation=%s.",
            ctx.generation,
        )
        if claimed is not None:
            self._execute_remove(state, claimed)
        else:
            self._schedule_pending_remove(state, raise_start_error=False)
        self._maybe_close_logs_when_idle(state)

    # ------------------------------------------------------------------
    # Pending / Active Remove scheduler
    # ------------------------------------------------------------------

    def _schedule_pending_remove(
        self,
        state: _RegistryProcessState,
        *,
        raise_start_error: bool,
    ) -> None:
        if not self._state_is_current(state):
            return

        start_error: Optional[Exception] = None
        failed_operation: Optional[_RemoveOperation] = None
        with state.state_lock:
            operation = state.pending_remove
            if state.active_remove is not None or operation is None:
                return

            # Only the same generation's stopping Worker may own this Remove.
            if operation.generation in state.stopping_workers:
                return

            scheduled = operation.thread
            if scheduled is not None:
                if scheduled.is_alive():
                    return
                state.cleanup_actors.discard(scheduled)
                if operation.thread is scheduled:
                    operation.thread = None

            thread = threading.Thread(
                target=self._run_cleanup_actor,
                args=(state, operation),
                name="flask-xxljob-registry-remove",
                daemon=True,
            )
            state.cleanup_actors.add(thread)
            operation.thread = thread
            try:
                # The actor first acquires state_lock, so registration,
                # association and successful start are atomic to the actor.
                thread.start()
            except Exception as exc:  # noqa: BLE001 - preserve exact failure
                state.cleanup_actors.discard(thread)
                if operation.thread is thread:
                    operation.thread = None
                if state.pending_remove is operation:
                    state.pending_remove = None
                if state.active_remove is operation:
                    state.active_remove = None
                failure = CallResult(
                    success=False,
                    error="Failed to start Registry cleanup actor.",
                    error_type=type(exc).__name__,
                )
                self._record_result_locked(state, failure, operation="local")
                failed_operation = operation
                start_error = exc

        if failed_operation is not None:
            failed_operation.done_event.set()
        if start_error is not None:
            self._logger.error(
                "XXL-JOB Registry cleanup actor failed to start "
                "exception_type=%s.",
                type(start_error).__name__,
            )
            if raise_start_error:
                raise start_error
            self._maybe_close_logs_when_idle(state)

    def _run_cleanup_actor(
        self,
        state: _RegistryProcessState,
        operation: _RemoveOperation,
    ) -> None:
        current_thread = threading.current_thread()
        claimed = False
        try:
            if not self._state_is_current(state):
                return
            with state.state_lock:
                if (
                    state.active_remove is None
                    and state.pending_remove is operation
                ):
                    state.pending_remove = None
                    state.active_remove = operation
                    claimed = True
            if claimed:
                self._execute_remove(state, operation)
        finally:
            if self._state_is_current(state):
                with state.state_lock:
                    state.cleanup_actors.discard(current_thread)
                    if operation.thread is current_thread:
                        operation.thread = None
                # A non-claiming actor must not leave a dead association that
                # strands a still-pending operation.
                self._schedule_pending_remove(
                    state, raise_start_error=False
                )
                self._maybe_close_logs_when_idle(state)

    def _execute_remove(
        self,
        state: _RegistryProcessState,
        operation: _RemoveOperation,
    ) -> None:
        if not self._state_is_current(state):
            return

        with state.network_lock:
            state.rpc_sequence += 1
            sequence = state.rpc_sequence
            try:
                result = self._admin_client.registry_remove(
                    self._build_request()
                )
            except Exception as exc:  # noqa: BLE001 - cleanup must terminate
                result = self._unexpected_result("removal", exc)

        if self._state_is_current(state):
            with state.state_lock:
                owns_active = state.active_remove is operation
                if (
                    owns_active
                    and sequence > state.last_applied_rpc_sequence
                ):
                    self._record_result_locked(
                        state, result, operation="remove"
                    )
                    state.last_applied_rpc_sequence = sequence
                # Completion may clear only its own Active identity.
                if state.active_remove is operation:
                    state.active_remove = None

        # done_event means both the RPC and this operation's local state
        # cleanup have ended.  It is deliberately set after releasing the lock.
        operation.done_event.set()
        self._log_rpc_result(result, "removal")
        self._schedule_pending_remove(state, raise_start_error=False)
        self._maybe_close_logs_when_idle(state)

    # ------------------------------------------------------------------
    # Status, finalization and log closing
    # ------------------------------------------------------------------

    def status_snapshot(self) -> Dict[str, Any]:
        """Return the unchanged public Registry status fields, locally only."""
        state = self._get_process_state()
        with state.state_lock:
            return {
                "registered": state.registered,
                "last_registry_time": state.last_registry_time,
                "last_registry_success": state.last_registry_success,
                "last_registry_admin_address": (
                    state.last_registry_admin_address
                ),
                "last_registry_error_type": state.last_registry_error_type,
                "last_registry_message": state.last_registry_message,
                "registry_thread_running": state.worker is not None,
            }

    @property
    def is_running(self) -> bool:
        state = self._get_process_state()
        with state.state_lock:
            return state.worker is not None

    def shutdown(self, *, deregister_on_exit: bool) -> None:
        """Best-effort, strictly non-blocking runtime finalization."""
        state = self._get_process_state()
        target_generation = 0
        should_validate_remove = False

        with state.state_lock:
            self._stop_local_locked(state)
            state.close_logs_when_idle = True
            target_generation = state.generation
            should_validate_remove = bool(
                self._config.enabled
                and deregister_on_exit
                and target_generation > 0
                and state.last_remove_requested_generation
                != target_generation
            )

        if should_validate_remove:
            try:
                self._config.validate_registry()
            except Exception as exc:  # noqa: BLE001 - finalizer is best effort
                failure = CallResult(
                    success=False,
                    error="Invalid Registry configuration during exit cleanup.",
                    error_type=type(exc).__name__,
                )
                self._record_local_failure(state, failure)
                self._logger.error(
                    "XXL-JOB exit removal configuration is invalid "
                    "exception_type=%s.",
                    type(exc).__name__,
                )
            else:
                operation: Optional[_RemoveOperation] = None
                with state.state_lock:
                    if (
                        state.generation == target_generation
                        and target_generation > 0
                        and state.last_remove_requested_generation
                        != target_generation
                    ):
                        operation = self._request_remove_locked(state)
                if operation is not None:
                    try:
                        self._schedule_pending_remove(
                            state, raise_start_error=True
                        )
                    except Exception as exc:  # noqa: BLE001
                        self._logger.error(
                            "XXL-JOB exit removal could not be scheduled "
                            "exception_type=%s.",
                            type(exc).__name__,
                        )

        self._maybe_close_logs_when_idle(state)

    def _maybe_close_logs_when_idle(
        self, state: Optional[_RegistryProcessState] = None
    ) -> None:
        current = self._get_process_state()
        if state is not None and state is not current:
            return
        state = current
        should_close = False
        with state.state_lock:
            if (
                state.close_logs_when_idle
                and state.worker is None
                and not state.stopping_workers
                and state.active_remove is None
                and state.pending_remove is None
                and not state.cleanup_actors
                and not state.logs_closed
            ):
                state.logs_closed = True
                should_close = True

        if should_close and self._close_logs is not None:
            try:
                self._close_logs()
            except Exception as exc:  # noqa: BLE001 - final cleanup is safe
                self._logger.error(
                    "XXL-JOB log cleanup failed exception_type=%s.",
                    type(exc).__name__,
                )

    def _log_rpc_result(self, result: CallResult, operation: str) -> None:
        if result.success:
            self._logger.info(
                "XXL-JOB executor %s succeeded via %s.",
                operation,
                result.address,
            )
        else:
            self._logger.warning(
                "XXL-JOB executor %s failed error_type=%s http_status=%s.",
                operation,
                result.error_type,
                result.http_status,
            )


__all__ = ["RegistryService"]

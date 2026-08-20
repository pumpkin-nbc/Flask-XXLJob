"""Process-local executor Registry lifecycle management."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set, Tuple

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
class _PreparedRegistryStart:
    """A started OS thread that is not yet a committed Registry Worker."""

    state: "_RegistryProcessState"
    context: _RegistryWorkerContext
    activate_event: threading.Event
    thread: threading.Thread


@dataclass(eq=False)
class _RemoveOperation:
    """One terminal/lifecycle Registry Remove ownership."""

    generation: int
    done_event: threading.Event
    thread: Optional[threading.Thread] = None
    result: Optional[CallResult] = None


@dataclass(eq=False)
class _RegisterCoordination:
    """Coordinate registers that overlap one generation cleanup boundary."""

    generation: int
    inflight_count: int = 0
    done_event: threading.Event = field(default_factory=threading.Event)
    cleanup_requested: bool = False


@dataclass(eq=False)
class _RegistryProcessState:
    """All Registry state that must be replaced at a PID boundary."""

    pid: int
    state_lock: threading.RLock = field(default_factory=threading.RLock)
    network_lock: threading.Lock = field(default_factory=threading.Lock)
    generation: int = 0
    # This marker belongs to the current cleanup responsibility, not to the
    # generation forever.  An accepted register may reopen the same generation.
    last_remove_requested_generation: Optional[int] = None
    last_successfully_removed_generation: Optional[int] = None
    last_successfully_removed_result: Optional[CallResult] = None
    register_coordination: Optional[_RegisterCoordination] = None
    prepared_start: Optional[_PreparedRegistryStart] = None
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

    @staticmethod
    def _internal_operation_result(message: str) -> CallResult:
        return CallResult(
            success=False,
            error=message,
            error_type="lifecycle",
            attempt_count=0,
        )

    def _join_register_coordination(
        self, state: _RegistryProcessState
    ) -> Tuple[Optional[_RegisterCoordination], int]:
        """Join the current generation's still-open register window."""
        detached_event: Optional[threading.Event] = None
        with state.state_lock:
            generation = state.generation
            coordination = state.register_coordination
            if (
                coordination is not None
                and coordination.generation != generation
            ):
                state.register_coordination = None
                detached_event = coordination.done_event
                coordination = None

            if coordination is not None:
                # A lifecycle cleanup request is the state-lock linearization
                # point that closes this coordination window.
                if coordination.cleanup_requested:
                    coordination = None
            else:
                # Every explicit one-shot register that reaches a live
                # generation before lifecycle cleanup is linearized must be
                # visible to that cleanup.  Generation zero is a cleanup scope
                # for manual registration, not a fabricated Worker lifecycle.
                # Worker renewals do not call this helper.
                coordination = _RegisterCoordination(generation=generation)
                state.register_coordination = coordination

            if coordination is not None:
                coordination.inflight_count += 1
                coordination.done_event.clear()

        if detached_event is not None:
            detached_event.set()
        return coordination, generation

    def _invalidate_successful_cleanup_locked(
        self,
        state: _RegistryProcessState,
        generation: int,
        coordination: Optional[_RegisterCoordination],
    ) -> bool:
        """Reopen cleanup responsibility after an accepted register."""
        if generation < 0 or state.generation != generation:
            return False

        invalidates_cached_success = (
            state.last_successfully_removed_generation == generation
        )
        restores_coordinated_responsibility = bool(
            coordination is not None
            and state.register_coordination is coordination
            and coordination.generation == generation
            and coordination.cleanup_requested
        )
        opens_manual_responsibility = bool(
            generation == 0
            and coordination is not None
            and state.register_coordination is coordination
            and coordination.generation == generation
        )
        if not (
            invalidates_cached_success
            or restores_coordinated_responsibility
            or opens_manual_responsibility
        ):
            return False

        state.last_successfully_removed_generation = None
        state.last_successfully_removed_result = None
        # This is a new remote state change, not a retry of the previous
        # cleanup responsibility.
        state.last_remove_requested_generation = None
        return True

    @staticmethod
    def _has_remove_for_generation_locked(
        state: _RegistryProcessState, generation: int
    ) -> bool:
        return bool(
            (
                state.active_remove is not None
                and state.active_remove.generation == generation
            )
            or (
                state.pending_remove is not None
                and state.pending_remove.generation == generation
            )
        )

    @staticmethod
    def _ensure_pending_remove_locked(
        state: _RegistryProcessState,
        generation: int,
    ) -> Optional[_RemoveOperation]:
        """Represent one lifecycle cleanup responsibility as Pending."""
        if generation == 0 and not state.registered:
            return None
        if state.last_successfully_removed_generation == generation:
            return None

        pending = state.pending_remove
        if pending is not None:
            if pending.generation == generation:
                state.last_remove_requested_generation = generation
                return pending
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

    def _reconcile_register_coordination_locked(
        self,
        state: _RegistryProcessState,
        coordination: _RegisterCoordination,
    ) -> Optional[_RemoveOperation]:
        """Reconcile local cleanup responsibility without I/O or waits."""
        if state.register_coordination is not coordination:
            return None
        generation = coordination.generation
        if state.generation != generation:
            state.register_coordination = None
            return None

        operation: Optional[_RemoveOperation] = None
        cleanup_required = generation > 0 or state.registered
        if (
            coordination.cleanup_requested
            and coordination.inflight_count == 0
            and cleanup_required
            and state.last_successfully_removed_generation != generation
        ):
            operation = self._ensure_pending_remove_locked(
                state, generation
            )

        if coordination.inflight_count == 0:
            cleanup_present = self._has_remove_for_generation_locked(
                state, generation
            )
            cleanup_satisfied = (
                state.last_successfully_removed_generation == generation
            )
            no_cleanup_responsibility = bool(
                generation == 0 and not state.registered
            )
            cleanup_attempt_finished = bool(
                coordination.cleanup_requested
                and not cleanup_present
                and state.last_remove_requested_generation == generation
            )
            if (
                not coordination.cleanup_requested
                or cleanup_satisfied
                or no_cleanup_responsibility
                or cleanup_attempt_finished
            ):
                state.register_coordination = None

        return operation

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
        coordination, generation = self._join_register_coordination(state)
        result, sequence = self._call_registry(state, remove=False)
        self._commit_one_shot(
            state,
            result,
            sequence,
            remove=False,
            generation=generation,
            coordination=coordination,
        )
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
        with state.state_lock:
            generation = state.generation
            # With no Worker, generation zero is the terminal cleanup scope for
            # an explicit registration. It uses the same Active/Pending owner
            # model without becoming a Worker generation.
            terminal_candidate = state.worker is None

        if terminal_candidate:
            return self._terminal_remove_result(state, generation)

        result, sequence = self._call_registry(state, remove=True)
        self._commit_one_shot(state, result, sequence, remove=True)
        self._log_rpc_result(result, "removal")
        return result

    def _terminal_remove_result(
        self,
        state: _RegistryProcessState,
        generation: int,
    ) -> CallResult:
        """Synchronously observe or own one terminal generation Remove."""
        while True:
            if not self._state_is_current(state):
                return self._internal_operation_result(
                    "Registry process state changed during executor removal."
                )

            wait_kind: Optional[str] = None
            wait_operation: Optional[_RemoveOperation] = None
            wait_event: Optional[threading.Event] = None
            cached_result: Optional[CallResult] = None
            owned_operation: Optional[_RemoveOperation] = None
            use_one_shot = False

            with state.state_lock:
                if state.generation != generation or state.worker is not None:
                    use_one_shot = True
                else:
                    coordination = state.register_coordination
                    if (
                        coordination is not None
                        and coordination.generation == generation
                        and coordination.inflight_count > 0
                    ):
                        wait_kind = "registers"
                        wait_event = coordination.done_event
                    elif (
                        state.last_successfully_removed_generation
                        == generation
                        and state.last_successfully_removed_result is not None
                    ):
                        cached_result = self._safe_result(
                            state.last_successfully_removed_result
                        )
                    elif state.active_remove is not None:
                        wait_operation = state.active_remove
                        wait_event = wait_operation.done_event
                        wait_kind = (
                            "same-active"
                            if wait_operation.generation == generation
                            else "other-active"
                        )
                    elif state.pending_remove is not None:
                        wait_operation = state.pending_remove
                        wait_event = wait_operation.done_event
                        wait_kind = (
                            "same-pending"
                            if wait_operation.generation == generation
                            else "other-pending"
                        )
                    else:
                        owned_operation = _RemoveOperation(
                            generation=generation,
                            done_event=threading.Event(),
                        )
                        state.active_remove = owned_operation

            if use_one_shot:
                result, sequence = self._call_registry(state, remove=True)
                self._commit_one_shot(
                    state, result, sequence, remove=True
                )
                self._log_rpc_result(result, "removal")
                return result
            if cached_result is not None:
                return cached_result
            if owned_operation is not None:
                self._execute_remove(state, owned_operation)
                return self._operation_result(owned_operation)

            if wait_kind == "same-pending":
                self._schedule_pending_remove(
                    state, raise_start_error=True
                )
            if wait_event is None:
                return self._internal_operation_result(
                    "Registry removal coordination did not provide an event."
                )
            wait_event.wait()

            if wait_kind in {"same-active", "same-pending"}:
                if (
                    wait_operation is not None
                    and wait_operation.result is not None
                ):
                    return self._safe_result(wait_operation.result)
                # A Pending operation may have been cancelled by a newer
                # lifecycle or by an accepted Active success.  Recheck all
                # state before deciding whether another RPC is still needed.
                if wait_kind == "same-active":
                    return self._internal_operation_result(
                        "Registry removal completed without a result."
                    )

    def _operation_result(self, operation: _RemoveOperation) -> CallResult:
        result = operation.result
        if result is None:
            return self._internal_operation_result(
                "Registry removal completed without a result."
            )
        return self._safe_result(result)

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
                self._logger.exception(
                    "Unexpected error during one-shot Registry RPC."
                )
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
        generation: Optional[int] = None,
        coordination: Optional[_RegisterCoordination] = None,
    ) -> None:
        if not self._state_is_current(state):
            if coordination is not None:
                coordination.done_event.set()
            return

        coordination_event: Optional[threading.Event] = None
        scheduled_operation: Optional[_RemoveOperation] = None
        with state.state_lock:
            completion_accepted = (
                sequence > state.last_applied_rpc_sequence
            )
            if completion_accepted:
                self._record_result_locked(
                    state,
                    result,
                    operation="remove" if remove else "register",
                )
                # Accepted failures carry the same ordering significance as
                # accepted successes.
                state.last_applied_rpc_sequence = sequence

                cleanup_mutation_allowed = bool(
                    not remove
                    and result.success
                    and generation is not None
                    and coordination is not None
                    and state.generation == generation
                    and coordination.generation == generation
                    and state.register_coordination is coordination
                )
                if cleanup_mutation_allowed:
                    assert generation is not None
                    self._invalidate_successful_cleanup_locked(
                        state, generation, coordination
                    )

            if coordination is not None:
                if coordination.inflight_count > 0:
                    coordination.inflight_count -= 1
                if state.register_coordination is coordination:
                    scheduled_operation = (
                        self._reconcile_register_coordination_locked(
                            state, coordination
                        )
                    )
                if coordination.inflight_count == 0:
                    # The Event is collected only after every state change and
                    # reconcile decision above is complete.
                    coordination_event = coordination.done_event

        if coordination_event is not None:
            coordination_event.set()
        if scheduled_operation is not None:
            self._schedule_pending_remove(state, raise_start_error=False)
        if coordination is not None:
            self._maybe_close_logs_when_idle(state)

    def register_once(self) -> bool:
        return self.register_once_result().success

    def remove_once(self) -> bool:
        return self.remove_once_result().success

    # ------------------------------------------------------------------
    # Renewal lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start one current renewal lifecycle and return without networking."""
        prepared = self._prepare_start()
        if prepared is None:
            return
        self._activate_prepared_start(prepared)

    def _prepare_start(self) -> Optional[_PreparedRegistryStart]:
        """Start an activation-gated Thread without committing a lifecycle."""
        if not self._config.enabled:
            return None
        self._config.validate_registry()
        state = self._get_process_state()

        with state.state_lock:
            existing = state.worker
            if existing is not None:
                if self._is_current_worker(state, existing):
                    return None
                # Repair is deliberately delayed until activation.  Prepare
                # owns only the candidate Thread and must not mutate the
                # previously committed lifecycle.

            if state.prepared_start is not None:
                # A different caller owns that Prepared token and is solely
                # responsible for activating it.
                return None

            candidate_generation = state.generation + 1
            ctx = _RegistryWorkerContext(
                generation=candidate_generation,
                stop_event=threading.Event(),
            )
            activate_event = threading.Event()
            thread = threading.Thread(
                target=self._prepared_worker_entry,
                args=(state, ctx, activate_event),
                name="flask-xxljob-registry",
                daemon=True,
            )
            ctx.thread = thread
            prepared = _PreparedRegistryStart(
                state=state,
                context=ctx,
                activate_event=activate_event,
                thread=thread,
            )
            state.prepared_start = prepared

            # Ownership publication and OS Thread creation are one short
            # state-lock linearization interval.  The target only waits on the
            # activation Event, so it cannot contend for this lock or issue an
            # Admin RPC before Thread.start() returns.
            try:
                thread.start()
            except Exception:
                if state.prepared_start is prepared:
                    state.prepared_start = None
                raise

        return prepared

    def _activate_prepared_start(
        self, prepared: _PreparedRegistryStart
    ) -> bool:
        """Commit a caller-owned Prepared Thread as the current Worker."""
        state = prepared.state
        # Never touch an inherited state lock or Event after a PID boundary.
        if os.getpid() != state.pid or self._get_process_state() is not state:
            return False

        cancelled: Optional[_RemoveOperation] = None
        detached_coordination_event: Optional[threading.Event] = None
        ctx = prepared.context
        with state.state_lock:
            if state.prepared_start is not prepared:
                # stop(), shutdown(), or another valid state transition won
                # the lock first.  Cancellation is an expected no-op result.
                return False

            if ctx.generation != state.generation + 1:
                raise RuntimeError(
                    "Prepared Registry generation no longer follows the "
                    "committed generation."
                )

            existing = state.worker
            if existing is not None:
                if self._is_current_worker(state, existing):
                    raise RuntimeError(
                        "A current Registry Worker appeared while a Prepared "
                        "Start retained activation ownership."
                    )
                # Preserve the former start() defensive repair, but only at
                # the point where this candidate is actually committed.
                state.worker = None
                state.stopping_workers[existing.generation] = existing
                existing.stop_event.set()

            state.generation = ctx.generation
            state.worker = ctx
            state.prepared_start = None

            coordination = state.register_coordination
            if coordination is not None:
                state.register_coordination = None
                detached_coordination_event = coordination.done_event

            # Pending and Active may coexist.  These are intentionally two
            # independent branches, not an if/elif pair.
            if state.pending_remove is not None:
                cancelled = state.pending_remove
                state.pending_remove = None
            if state.active_remove is not None:
                ctx.wait_remove_event = state.active_remove.done_event

        if cancelled is not None:
            cancelled.done_event.set()
        if detached_coordination_event is not None:
            detached_coordination_event.set()
        prepared.activate_event.set()
        self._logger.info(
            "XXL-JOB registry lifecycle started generation=%s.",
            ctx.generation,
        )
        return True

    def _cancel_prepared_start(
        self, prepared: _PreparedRegistryStart
    ) -> bool:
        """Cancel only a Prepared token still owned by its original state."""
        state = prepared.state
        if os.getpid() != state.pid or self._get_process_state() is not state:
            return False

        with state.state_lock:
            if state.prepared_start is not prepared:
                return False
            state.prepared_start = None

        prepared.context.stop_event.set()
        prepared.activate_event.set()
        return True

    @staticmethod
    def _join_prepared_start(
        prepared: _PreparedRegistryStart, timeout: float = 1.0
    ) -> None:
        """Boundedly join a successfully started, uncommitted Thread."""
        if os.getpid() != prepared.state.pid:
            return
        if prepared.thread is threading.current_thread():
            return
        prepared.thread.join(timeout=timeout)

    def _prepared_worker_entry(
        self,
        state: _RegistryProcessState,
        ctx: _RegistryWorkerContext,
        activate_event: threading.Event,
    ) -> None:
        """Wait for activation and distinguish cancellation from Worker stop."""
        activate_event.wait()

        # Check the immutable PID before acquiring or reading inherited
        # synchronization objects.
        if os.getpid() != state.pid or self._get_process_state() is not state:
            return

        with state.state_lock:
            committed_worker = bool(
                state.worker is ctx
                or state.stopping_workers.get(ctx.generation) is ctx
            )

        if not committed_worker:
            # This candidate never owned a committed generation, so it has no
            # Worker/Remove/Scheduler/log lifecycle to finish.
            return

        # Even a stop-before-first-RPC is a committed Worker lifecycle.  The
        # first stop/ownership checks remain inside _run_worker's try/finally.
        self._run_worker(state, ctx)

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
                self._logger.exception(
                    "Unexpected error during Registry renewal."
                )
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
                    if result.success:
                        self._invalidate_successful_cleanup_locked(
                            state, ctx.generation, None
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
        prepared_to_cancel: Optional[_PreparedRegistryStart] = None
        with state.state_lock:
            prepared_to_cancel = state.prepared_start
            if prepared_to_cancel is not None:
                state.prepared_start = None
            self._stop_local_locked(state)
            if remove:
                operation = self._request_remove_locked(state)

        if prepared_to_cancel is not None:
            prepared_to_cancel.context.stop_event.set()
            prepared_to_cancel.activate_event.set()
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

    def _request_remove_locked(
        self,
        state: _RegistryProcessState,
    ) -> Optional[_RemoveOperation]:
        generation = state.generation

        coordination = state.register_coordination
        if (
            coordination is not None
            and coordination.generation == generation
        ):
            coordination.cleanup_requested = True
            operation = self._reconcile_register_coordination_locked(
                state, coordination
            )
            if operation is not None:
                return operation
            if (
                state.last_successfully_removed_generation == generation
                or coordination.inflight_count > 0
            ):
                return None

        if state.last_successfully_removed_generation == generation:
            return None
        if generation == 0 and not state.registered:
            return None
        return self._ensure_pending_remove_locked(state, generation)

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
                operation.result = self._safe_result(failure)
                self._record_result_locked(state, failure, operation="local")
                coordination = state.register_coordination
                if (
                    coordination is not None
                    and coordination.generation == operation.generation
                ):
                    self._reconcile_register_coordination_locked(
                        state, coordination
                    )
                failed_operation = operation
                start_error = exc

        if failed_operation is not None:
            failed_operation.done_event.set()
        if start_error is not None:
            self._logger.error(
                "XXL-JOB Registry cleanup actor failed to start "
                "exception_type=%s.",
                type(start_error).__name__,
                exc_info=(
                    type(start_error),
                    start_error,
                    start_error.__traceback__,
                ),
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
                operation.result = self._internal_operation_result(
                    "Registry process state changed before cleanup actor claim."
                )
                operation.done_event.set()
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
            operation.result = self._internal_operation_result(
                "Registry process state changed before executor removal."
            )
            operation.done_event.set()
            return

        with state.network_lock:
            state.rpc_sequence += 1
            sequence = state.rpc_sequence
            try:
                result = self._admin_client.registry_remove(
                    self._build_request()
                )
            except Exception as exc:  # noqa: BLE001 - cleanup must terminate
                self._logger.exception(
                    "Unexpected error during Registry removal."
                )
                result = self._unexpected_result("removal", exc)

        cancelled_pending = self._complete_remove_operation(
            state, operation, result, sequence
        )

        # done_event means both the RPC and this operation's local state
        # cleanup have ended.  It is deliberately set after releasing the lock.
        operation.done_event.set()
        if cancelled_pending is not None:
            cancelled_pending.done_event.set()
        self._log_rpc_result(result, "removal")
        self._schedule_pending_remove(state, raise_start_error=False)
        self._maybe_close_logs_when_idle(state)

    def _complete_remove_operation(
        self,
        state: _RegistryProcessState,
        operation: _RemoveOperation,
        result: CallResult,
        sequence: int,
    ) -> Optional[_RemoveOperation]:
        """Finish one Active Remove after its network lock is released."""
        safe_result = self._safe_result(result)
        cancelled_pending: Optional[_RemoveOperation] = None
        if self._state_is_current(state):
            with state.state_lock:
                # Operation-local completion is independent from whether this
                # result is still allowed to update the process-wide snapshot.
                operation.result = safe_result
                owns_active = state.active_remove is operation
                completion_accepted = bool(
                    owns_active
                    and sequence > state.last_applied_rpc_sequence
                )
                if completion_accepted:
                    self._record_result_locked(
                        state, result, operation="remove"
                    )
                    state.last_applied_rpc_sequence = sequence

                    cleanup_satisfied = bool(
                        safe_result.success
                        and operation.generation >= 0
                        and state.generation == operation.generation
                        and state.worker is None
                    )
                    if cleanup_satisfied:
                        state.last_remove_requested_generation = (
                            operation.generation
                        )
                        state.last_successfully_removed_generation = (
                            operation.generation
                        )
                        state.last_successfully_removed_result = (
                            self._safe_result(safe_result)
                        )
                        pending = state.pending_remove
                        if (
                            pending is not None
                            and pending.generation == operation.generation
                        ):
                            state.pending_remove = None
                            cancelled_pending = pending

                # Completion may clear only its own Active identity.
                if state.active_remove is operation:
                    state.active_remove = None

                coordination = state.register_coordination
                if (
                    coordination is not None
                    and coordination.generation == operation.generation
                ):
                    self._reconcile_register_coordination_locked(
                        state, coordination
                    )
        else:
            # Never acquire a replaced ProcessState lock, but always complete
            # this private Operation for any observers that still hold it.
            operation.result = safe_result
        return cancelled_pending

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
        prepared_to_cancel: Optional[_PreparedRegistryStart] = None

        with state.state_lock:
            prepared_to_cancel = state.prepared_start
            if prepared_to_cancel is not None:
                state.prepared_start = None
            self._stop_local_locked(state)
            state.close_logs_when_idle = True
            target_generation = state.generation
            coordination = state.register_coordination
            matching_coordination = bool(
                coordination is not None
                and coordination.generation == target_generation
            )
            # shutdown's state-lock mutation is the non-blocking linearization
            # point that closes this register window, including generation 0.
            if (
                self._config.enabled
                and deregister_on_exit
                and matching_coordination
            ):
                assert coordination is not None
                coordination.cleanup_requested = True
            inflight_register = bool(
                matching_coordination
                and coordination is not None
                and coordination.inflight_count > 0
            )
            cleanup_satisfied = (
                state.last_successfully_removed_generation
                == target_generation
            )
            cleanup_required = bool(
                target_generation > 0
                or (target_generation == 0 and state.registered)
            )
            should_validate_remove = bool(
                self._config.enabled
                and deregister_on_exit
                and (
                    inflight_register
                    or (
                        cleanup_required
                        and not cleanup_satisfied
                        and state.last_remove_requested_generation
                        != target_generation
                    )
                )
            )

        if prepared_to_cancel is not None:
            prepared_to_cancel.context.stop_event.set()
            prepared_to_cancel.activate_event.set()

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
                    if state.generation == target_generation:
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
                and state.prepared_start is None
                and state.worker is None
                and not state.stopping_workers
                and state.active_remove is None
                and state.pending_remove is None
                and not state.cleanup_actors
                and state.register_coordination is None
                and not state.logs_closed
            ):
                state.logs_closed = True
                should_close = True

        if should_close and self._close_logs is not None:
            try:
                self._close_logs()
            except Exception:  # noqa: BLE001 - final cleanup is safe
                self._logger.exception("XXL-JOB log cleanup failed.")

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

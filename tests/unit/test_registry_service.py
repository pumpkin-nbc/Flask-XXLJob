"""RegistryService process lifecycle, ordering, and cleanup tests."""

from __future__ import annotations

import threading
import time

import pytest

from flask_xxljob.client import CallResult
from flask_xxljob.config import XXLJobConfig
from flask_xxljob.exceptions import XXLJobConfigError
from flask_xxljob.registry.registry_service import (
    RegistryService,
    _PreparedRegistryStart,
    _RegisterCoordination,
    _RegistryWorkerContext,
    _RemoveOperation,
)


def make_config(**overrides):
    mapping = {
        "XXL_JOB_ADMIN_ADDRESSES": ["http://a:8080"],
        "XXL_JOB_EXECUTOR_APP_NAME": "app",
        "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
        "XXL_JOB_AUTO_REGISTER": False,
        "XXL_JOB_REGISTRY_INTERVAL": 3600,
    }
    mapping.update(overrides)
    return XXLJobConfig.from_mapping(mapping)


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


class FakeAdmin:
    def __init__(self, registry_success=True, remove_success=True):
        self.registry_success = registry_success
        self.remove_success = remove_success
        self.registry_calls = 0
        self.remove_calls = 0

    def registry(self, request):
        self.registry_calls += 1
        return CallResult(
            success=self.registry_success,
            address="http://a:8080",
            error=None if self.registry_success else "register failed",
            error_type=None if self.registry_success else "business",
        )

    def registry_remove(self, request):
        self.remove_calls += 1
        return CallResult(
            success=self.remove_success,
            address="http://a:8080",
            error=None if self.remove_success else "remove failed",
            error_type=None if self.remove_success else "business",
        )


class RaisingAdmin(FakeAdmin):
    def registry(self, request):
        self.registry_calls += 1
        raise RuntimeError("register exploded")

    def registry_remove(self, request):
        self.remove_calls += 1
        raise RuntimeError("remove exploded")


class BlockingRegistryAdmin(FakeAdmin):
    def __init__(self, result=True):
        super().__init__(registry_success=result)
        self.started = threading.Event()
        self.release = threading.Event()

    def registry(self, request):
        self.registry_calls += 1
        self.started.set()
        self.release.wait(timeout=5)
        return CallResult(
            success=self.registry_success,
            address="http://a:8080",
            error=None if self.registry_success else "blocked failure",
            error_type=None if self.registry_success else "network",
        )


class PartiallySuccessfulBlockingRegistryAdmin(FakeAdmin):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def registry(self, request):
        self.registry_calls += 1
        call_number = self.registry_calls
        self.started.set()
        if call_number == 1:
            self.release.wait(timeout=5)
        success = call_number == 1
        return CallResult(
            success=success,
            address="http://a:8080",
            error=None if success else "register failed",
            error_type=None if success else "business",
        )


class BlockingRemoveAdmin(FakeAdmin):
    def __init__(self, remove_success=True):
        super().__init__(remove_success=remove_success)
        self.remove_started = threading.Event()
        self.remove_release = threading.Event()

    def registry_remove(self, request):
        self.remove_calls += 1
        self.remove_started.set()
        self.remove_release.wait(timeout=5)
        return CallResult(
            success=self.remove_success,
            address="http://a:8080",
            error=None if self.remove_success else "remove failed",
            error_type=None if self.remove_success else "business",
        )


class FirstRemoveBlocksAdmin(FakeAdmin):
    def __init__(self):
        super().__init__()
        self.first_remove_started = threading.Event()
        self.first_remove_release = threading.Event()

    def registry_remove(self, request):
        self.remove_calls += 1
        if self.remove_calls == 1:
            self.first_remove_started.set()
            self.first_remove_release.wait(timeout=5)
        return CallResult(success=True, address="http://a:8080")


class OldActiveNewGenerationAdmin(BlockingRemoveAdmin):
    def __init__(self):
        super().__init__()
        self.second_registry_started = threading.Event()
        self.second_registry_release = threading.Event()

    def registry(self, request):
        self.registry_calls += 1
        if self.registry_calls == 2:
            self.second_registry_started.set()
            self.second_registry_release.wait(timeout=5)
        return CallResult(success=True, address="http://a:8080")


class ScriptedWaitEvent:
    """Event-shaped test double that permits one renewal before stopping."""

    def __init__(self):
        self._set = False
        self.timeouts = []

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, timeout):
        self.timeouts.append(timeout)
        if len(self.timeouts) >= 2:
            self._set = True
            return True
        return False


def test_sync_register_and_remove_update_snapshot_without_generation():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)

    assert service.register_once_result().success is True
    state = service._get_process_state()
    assert state.registered is True
    assert state.generation == 0
    assert state.rpc_sequence == 1
    assert state.last_applied_rpc_sequence == 1

    assert service.remove_once_result().success is True
    assert state.registered is False
    assert state.generation == 0
    assert state.rpc_sequence == 2
    assert state.last_applied_rpc_sequence == 2


@pytest.mark.parametrize("remove", [False, True])
def test_sync_failure_preserves_registered_and_advances_sequence(remove):
    admin = FakeAdmin(registry_success=False, remove_success=False)
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.registered = True

    result = (
        service.remove_once_result()
        if remove
        else service.register_once_result()
    )

    assert result.success is False
    assert state.registered is True
    assert state.rpc_sequence == 1
    assert state.last_applied_rpc_sequence == 1
    assert state.last_error is not None


@pytest.mark.parametrize("remove", [False, True])
def test_sync_unexpected_exception_is_safe_and_ordered(remove):
    service = RegistryService(make_config(), RaisingAdmin())
    state = service._get_process_state()

    result = (
        service.remove_once_result()
        if remove
        else service.register_once_result()
    )

    assert result.success is False
    assert result.error_type == "RuntimeError"
    assert "exploded" not in (result.error or "")
    assert state.last_applied_rpc_sequence == 1


@pytest.mark.parametrize("method_name", ["register_once_result", "remove_once_result"])
@pytest.mark.parametrize("registered", [False, True])
def test_disabled_sync_api_updates_only_local_safe_snapshot(
    method_name, registered
):
    config = make_config(XXL_JOB_ENABLED=False)
    admin = FakeAdmin()
    service = RegistryService(config, admin)
    state = service._get_process_state()
    state.registered = registered
    state.generation = 7

    result = getattr(service, method_name)()

    assert result == CallResult(
        success=False,
        error="Flask-XXLJob is disabled.",
        error_type="config",
        attempt_count=0,
    )
    assert state.registered is registered
    assert state.generation == 7
    assert state.rpc_sequence == 0
    assert state.last_applied_rpc_sequence == 0
    assert state.last_result == result
    assert state.last_error == result
    assert admin.registry_calls == 0
    assert admin.remove_calls == 0


def test_disabled_start_and_both_stop_modes_are_true_noops():
    config = XXLJobConfig.from_mapping(
        {
            "XXL_JOB_ENABLED": False,
            "XXL_JOB_AUTO_REGISTER": True,
            "XXL_JOB_ADMIN_ADDRESSES": [],
        }
    )
    admin = FakeAdmin()
    service = RegistryService(config, admin)
    original = service._process_state

    assert service.start() is None
    assert service.stop(remove=False) is None
    assert service.stop(remove=True) is None
    assert service._process_state is original
    assert admin.registry_calls == admin.remove_calls == 0


@pytest.mark.parametrize(
    "method",
    [
        lambda service: service.start(),
        lambda service: service.register_once_result(),
        lambda service: service.remove_once_result(),
        lambda service: service.stop(remove=True),
    ],
)
def test_enabled_remote_entrypoints_validate_before_side_effects(method, mocker):
    config = XXLJobConfig.from_mapping(
        {
            "XXL_JOB_AUTO_REGISTER": False,
            "XXL_JOB_ADMIN_ADDRESSES": [],
        }
    )
    admin = FakeAdmin()
    service = RegistryService(config, admin)
    thread = mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread"
    )

    with pytest.raises(XXLJobConfigError):
        method(service)

    thread.assert_not_called()
    assert admin.registry_calls == admin.remove_calls == 0


def test_start_returns_while_first_admin_call_is_blocked():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)

    service.start()

    assert admin.started.wait(timeout=1)
    assert service.is_running is True
    admin.release.set()
    service.stop()
    wait_for(lambda: not service._get_process_state().stopping_workers)


def test_concurrent_start_creates_one_current_worker():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    barrier = threading.Barrier(9)

    def start():
        barrier.wait()
        service.start()

    callers = [threading.Thread(target=start) for _ in range(8)]
    for caller in callers:
        caller.start()
    barrier.wait()
    for caller in callers:
        caller.join(timeout=1)

    state = service._get_process_state()
    assert state.generation == 1
    assert state.worker is not None
    assert admin.started.wait(timeout=1)
    assert admin.registry_calls == 1
    service.stop()
    admin.release.set()
    wait_for(lambda: not state.stopping_workers)


def test_registered_snapshot_does_not_prevent_a_new_start():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.registered = True

    service.start()

    assert state.worker is not None
    assert state.generation == 1
    service.stop()
    admin.release.set()
    wait_for(lambda: not state.stopping_workers)


def test_thread_start_failure_does_not_commit_or_cancel_pending(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    pending = _RemoveOperation(0, threading.Event())
    state.pending_remove = pending

    failed_thread = mocker.Mock()
    failed_thread.start.side_effect = RuntimeError("cannot start")
    thread_factory = mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        return_value=failed_thread,
    )

    with pytest.raises(RuntimeError, match="cannot start"):
        service.start()

    assert state.generation == 0
    assert state.prepared_start is None
    assert state.worker is None
    assert state.pending_remove is pending
    assert pending.done_event.is_set() is False
    failed_thread.join.assert_not_called()

    mocker.stop(thread_factory)
    service.start()
    assert state.generation == 1
    assert state.pending_remove is None
    assert pending.done_event.is_set() is True
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_prepare_is_private_and_does_not_mutate_committed_lifecycle():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    pending = _RemoveOperation(3, threading.Event())
    active = _RemoveOperation(2, threading.Event())
    coordination = _RegisterCoordination(generation=3)
    cached = CallResult(success=True, address="http://a:8080")
    state.generation = 3
    state.pending_remove = pending
    state.active_remove = active
    state.last_remove_requested_generation = 3
    state.last_successfully_removed_generation = 3
    state.last_successfully_removed_result = cached
    state.register_coordination = coordination
    state.registered = True
    state.rpc_sequence = 7
    state.last_applied_rpc_sequence = 6

    prepared = service._prepare_start()

    assert isinstance(prepared, _PreparedRegistryStart)
    assert state.prepared_start is prepared
    assert prepared.context.generation == 4
    assert state.generation == 3
    assert state.worker is None
    assert state.pending_remove is pending
    assert state.active_remove is active
    assert state.last_remove_requested_generation == 3
    assert state.last_successfully_removed_generation == 3
    assert state.last_successfully_removed_result is cached
    assert state.register_coordination is coordination
    assert state.registered is True
    assert state.rpc_sequence == 7
    assert state.last_applied_rpc_sequence == 6

    assert service._cancel_prepared_start(prepared) is True
    service._join_prepared_start(prepared)
    assert prepared.thread.is_alive() is False


def test_second_start_cannot_activate_another_callers_prepared(mocker):
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    prepared = service._prepare_start()
    assert prepared is not None
    activate = mocker.spy(service, "_activate_prepared_start")

    service.start()

    activate.assert_not_called()
    state = service._get_process_state()
    assert state.prepared_start is prepared
    assert state.generation == 0
    assert state.worker is None
    assert service.is_running is False
    assert service.status_snapshot()["registry_thread_running"] is False
    assert admin.registry_calls == 0

    assert service._activate_prepared_start(prepared) is True
    assert admin.started.wait(timeout=1)
    service.stop()
    admin.release.set()
    wait_for(lambda: not state.stopping_workers)


def test_prepare_publication_and_thread_start_share_state_lock(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    start_entered = threading.Event()
    release_start = threading.Event()
    prepared_result = []

    class BlockingStartThread:
        def __init__(self, *args, **kwargs):
            self.name = kwargs.get("name")

        def start(self):
            start_entered.set()
            release_start.wait(timeout=2)

        def join(self, timeout=None):
            return None

    real_thread = threading.Thread
    mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        BlockingStartThread,
    )

    caller = real_thread(
        target=lambda: prepared_result.append(service._prepare_start())
    )
    caller.start()
    assert start_entered.wait(timeout=1)

    assert state.state_lock.acquire(blocking=False) is False

    release_start.set()
    caller.join(timeout=1)
    assert len(prepared_result) == 1
    prepared = prepared_result[0]
    assert isinstance(prepared, _PreparedRegistryStart)
    assert service._cancel_prepared_start(prepared) is True


def test_cancelled_unactivated_prepared_exits_without_worker_finally(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    finish = mocker.spy(service, "_finish_worker")
    schedule = mocker.spy(service, "_schedule_pending_remove")
    prepared = service._prepare_start()
    assert prepared is not None

    assert service._cancel_prepared_start(prepared) is True
    service._join_prepared_start(prepared)

    state = service._get_process_state()
    assert prepared.thread.is_alive() is False
    assert state.prepared_start is None
    assert state.generation == 0
    assert state.worker is None
    assert not state.stopping_workers
    assert admin.registry_calls == admin.remove_calls == 0
    finish.assert_not_called()
    schedule.assert_not_called()


def test_stale_prepared_cancel_does_not_stop_activated_worker():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    prepared = service._prepare_start()
    assert prepared is not None

    assert service._activate_prepared_start(prepared) is True
    assert service._cancel_prepared_start(prepared) is False
    assert prepared.context.stop_event.is_set() is False
    assert admin.started.wait(timeout=1)

    service.stop()
    admin.release.set()
    wait_for(lambda: not service._get_process_state().stopping_workers)


def test_stop_after_activation_commit_still_runs_worker_finally(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    finish = mocker.spy(service, "_finish_worker")
    prepared = service._prepare_start()
    assert prepared is not None
    original_set = prepared.activate_event.set
    activation_reached_event = threading.Event()
    release_activation_event = threading.Event()

    def delayed_set():
        activation_reached_event.set()
        release_activation_event.wait(timeout=2)
        original_set()

    prepared.activate_event.set = delayed_set
    activated = []
    caller = threading.Thread(
        target=lambda: activated.append(
            service._activate_prepared_start(prepared)
        )
    )
    caller.start()
    assert activation_reached_event.wait(timeout=1)

    state = service._get_process_state()
    assert state.worker is prepared.context
    service.stop()
    assert state.stopping_workers[1] is prepared.context

    release_activation_event.set()
    caller.join(timeout=1)
    prepared.thread.join(timeout=1)

    assert activated == [True]
    assert admin.registry_calls == 0
    finish.assert_called_once_with(state, prepared.context)
    assert state.prepared_start is None
    assert state.worker is None
    assert not state.stopping_workers


def test_old_committed_worker_finishes_without_overwriting_new_generation():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    old = service._prepare_start()
    assert old is not None
    original_set = old.activate_event.set
    old_activation_committed = threading.Event()
    release_old_worker = threading.Event()

    def delayed_set():
        old_activation_committed.set()
        release_old_worker.wait(timeout=2)
        original_set()

    old.activate_event.set = delayed_set
    old_caller = threading.Thread(
        target=lambda: service._activate_prepared_start(old)
    )
    old_caller.start()
    assert old_activation_committed.wait(timeout=1)

    state = service._get_process_state()
    service.stop()
    service.start()
    assert state.generation == 2
    current = state.worker
    assert current is not None and current.generation == 2
    assert admin.started.wait(timeout=1)

    release_old_worker.set()
    old_caller.join(timeout=1)
    old.thread.join(timeout=1)

    assert admin.registry_calls == 1
    assert state.worker is current
    assert 1 not in state.stopping_workers
    assert state.generation == 2

    service.stop()
    admin.release.set()
    wait_for(lambda: not state.stopping_workers)


def test_shutdown_cancels_generation_zero_prepared_without_remove():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    prepared = service._prepare_start()
    assert prepared is not None

    service.shutdown(deregister_on_exit=True)
    service._join_prepared_start(prepared)

    state = service._get_process_state()
    assert state.prepared_start is None
    assert state.generation == 0
    assert state.worker is None
    assert admin.registry_calls == admin.remove_calls == 0


def test_shutdown_cancels_prepared_but_cleans_old_committed_generation():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.registered = True
    prepared = service._prepare_start()
    assert prepared is not None
    assert prepared.context.generation == 2

    service.shutdown(deregister_on_exit=True)
    service._join_prepared_start(prepared)
    wait_for(lambda: admin.remove_calls == 1)
    wait_for(
        lambda: state.active_remove is None
        and state.pending_remove is None
        and not state.cleanup_actors
    )

    assert state.generation == 1
    assert state.last_successfully_removed_generation == 1
    assert state.prepared_start is None
    assert admin.registry_calls == 0


def test_prepared_ownership_prevents_early_log_idle_close(mocker):
    closed = mocker.Mock()
    service = RegistryService(make_config(), FakeAdmin(), close_logs=closed)
    prepared = service._prepare_start()
    assert prepared is not None
    state = service._get_process_state()
    state.close_logs_when_idle = True

    service._maybe_close_logs_when_idle(state)

    closed.assert_not_called()
    assert state.logs_closed is False

    assert service._cancel_prepared_start(prepared) is True
    service._join_prepared_start(prepared)
    service._maybe_close_logs_when_idle(state)
    closed.assert_called_once_with()
    assert state.logs_closed is True


def test_stop_is_immediately_local_and_tracks_stopping_worker():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()
    ctx = state.worker

    service.stop(remove=False)

    assert service.is_running is False
    assert service.status_snapshot()["registry_thread_running"] is False
    assert state.generation == 1
    assert state.stopping_workers[1] is ctx
    assert state.registered is False
    admin.release.set()
    wait_for(lambda: 1 not in state.stopping_workers)
    assert state.rpc_sequence == 1
    assert state.last_applied_rpc_sequence == 0


def test_stop_does_not_change_a_true_registered_snapshot():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.registered = True

    service.stop(remove=False)

    assert service.status_snapshot()["registered"] is True
    assert service.status_snapshot()["registry_thread_running"] is False


def test_worker_failure_is_accepted_and_worker_keeps_running():
    admin = FakeAdmin(registry_success=False)
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()

    assert state.registered is False
    assert state.last_applied_rpc_sequence == 1
    assert service.is_running is True
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_worker_failure_retries_after_the_configured_interval():
    admin = FakeAdmin(registry_success=False)
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    stop_event = ScriptedWaitEvent()
    ctx = _RegistryWorkerContext(1, stop_event)
    state.generation = 1
    state.worker = ctx

    service._run_worker(state, ctx)

    assert admin.registry_calls == 2
    assert stop_event.timeouts == [3600, 3600]
    assert state.registered is False
    assert state.last_applied_rpc_sequence == 2
    assert state.worker is None


def test_old_inflight_worker_result_cannot_pollute_new_generation():
    admin = BlockingRegistryAdmin(result=False)
    service = RegistryService(make_config(), admin)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()

    service.stop()
    admin.registry_success = True
    service.start()
    assert state.generation == 2
    admin.release.set()
    wait_for(lambda: admin.registry_calls >= 2)
    wait_for(lambda: state.last_applied_rpc_sequence >= 2)

    assert state.registered is True
    assert state.worker is not None
    assert state.worker.generation == 2
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_plain_stop_never_deregisters():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)

    service.stop()
    wait_for(lambda: not service._get_process_state().stopping_workers)

    assert admin.remove_calls == 0


def test_stop_remove_is_background_and_worker_claims_same_generation():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()

    service.stop(remove=True)

    operation = state.pending_remove
    assert operation is not None
    assert operation.generation == 1
    assert admin.remove_calls == 0
    admin.release.set()
    assert operation.done_event.wait(timeout=1)
    assert admin.remove_calls == 1
    assert state.last_remove_requested_generation == 1


def test_remove_can_be_requested_after_plain_stop_while_worker_is_stopping():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()

    service.stop(remove=False)
    assert 1 in state.stopping_workers
    service.stop(remove=True)
    operation = state.pending_remove

    assert operation is not None
    admin.release.set()
    assert operation.done_event.wait(timeout=1)
    assert admin.remove_calls == 1


def test_remove_can_be_requested_after_worker_has_fully_exited():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=False)
    wait_for(lambda: not state.stopping_workers)

    service.stop(remove=True)

    wait_for(lambda: admin.remove_calls == 1)
    wait_for(lambda: state.active_remove is None)
    assert state.last_remove_requested_generation == 1


def test_terminal_sync_remove_success_is_reused_by_shutdown():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop()
    wait_for(lambda: not state.stopping_workers)

    result = service.remove_once_result()
    sequence = state.rpc_sequence
    service.shutdown(deregister_on_exit=True)

    time.sleep(0.02)
    assert result.success is True
    assert admin.remove_calls == 1
    assert state.rpc_sequence == sequence
    assert state.last_remove_requested_generation == 1
    assert state.last_successfully_removed_generation == 1
    assert state.last_successfully_removed_result is not result


def test_completed_background_remove_is_reused_by_terminal_sync_call():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()

    service.stop(remove=True)
    wait_for(lambda: state.last_successfully_removed_generation == 1)
    sequence = state.rpc_sequence

    result = service.remove_once_result()

    assert result.success is True
    assert admin.remove_calls == 1
    assert state.rpc_sequence == sequence
    result.success = False
    assert state.last_successfully_removed_result is not None
    assert state.last_successfully_removed_result.success is True


def test_accepted_register_reopens_same_generation_cleanup_eligibility():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop()
    wait_for(lambda: not state.stopping_workers)
    assert service.remove_once_result().success is True
    assert state.last_successfully_removed_generation == 1

    assert service.register_once_result().success is True

    assert state.registered is True
    assert state.last_successfully_removed_generation is None
    assert state.last_successfully_removed_result is None
    assert state.last_remove_requested_generation is None

    service.shutdown(deregister_on_exit=True)
    wait_for(lambda: admin.remove_calls == 2)
    wait_for(lambda: state.last_successfully_removed_generation == 1)
    assert state.last_successfully_removed_generation == 1


def test_terminal_sync_failure_waits_for_later_shutdown_to_retry():
    admin = FakeAdmin(remove_success=False)
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop()
    wait_for(lambda: not state.stopping_workers)

    result = service.remove_once_result()

    assert result.success is False
    assert admin.remove_calls == 1
    assert state.pending_remove is None
    assert state.last_remove_requested_generation is None
    admin.remove_success = True

    service.shutdown(deregister_on_exit=True)
    wait_for(lambda: admin.remove_calls == 2)
    wait_for(lambda: state.last_successfully_removed_generation == 1)
    assert state.last_successfully_removed_generation == 1


def test_shutdown_active_is_observed_by_terminal_sync_remove():
    admin = BlockingRemoveAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=True)
    assert admin.remove_started.wait(timeout=1)
    results = []
    caller = threading.Thread(
        target=lambda: results.append(service.remove_once_result())
    )
    caller.start()

    time.sleep(0.02)
    assert admin.remove_calls == 1
    admin.remove_release.set()
    caller.join(timeout=1)

    assert not caller.is_alive()
    assert results[0].success is True
    assert admin.remove_calls == 1
    assert state.last_successfully_removed_generation == 1


def test_sync_active_success_cancels_concurrent_shutdown_fallback():
    admin = BlockingRemoveAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop()
    wait_for(lambda: not state.stopping_workers)
    results = []
    caller = threading.Thread(
        target=lambda: results.append(service.remove_once_result())
    )
    caller.start()
    assert admin.remove_started.wait(timeout=1)

    service.shutdown(deregister_on_exit=True)
    pending = state.pending_remove
    assert pending is not None
    admin.remove_release.set()
    caller.join(timeout=1)

    assert results[0].success is True
    assert pending.done_event.wait(timeout=1)
    assert admin.remove_calls == 1
    assert state.pending_remove is None


def test_sync_active_failure_preserves_one_shutdown_fallback():
    admin = BlockingRemoveAdmin(remove_success=False)
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop()
    wait_for(lambda: not state.stopping_workers)
    results = []
    caller = threading.Thread(
        target=lambda: results.append(service.remove_once_result())
    )
    caller.start()
    assert admin.remove_started.wait(timeout=1)

    service.shutdown(deregister_on_exit=True)
    pending = state.pending_remove
    assert pending is not None
    admin.remove_release.set()
    caller.join(timeout=1)

    assert results[0].success is False
    assert pending.done_event.wait(timeout=1)
    assert admin.remove_calls == 2
    time.sleep(0.02)
    assert admin.remove_calls == 2


def test_generation_zero_never_creates_automatic_remove():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)

    service.stop(remove=True)

    state = service._get_process_state()
    assert state.generation == 0
    assert state.pending_remove is None
    assert state.active_remove is None
    assert admin.remove_calls == 0


def test_same_generation_automatic_remove_is_never_retried_after_failure():
    admin = FakeAdmin(remove_success=False)
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()

    service.stop(remove=True)
    wait_for(lambda: admin.remove_calls == 1)
    wait_for(lambda: state.active_remove is None)
    service.stop(remove=True)

    time.sleep(0.02)
    assert admin.remove_calls == 1
    assert state.last_remove_requested_generation == 1


def test_new_generation_gets_its_own_remove_eligibility():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    service.stop(remove=True)
    wait_for(lambda: admin.remove_calls == 1)

    service.start()
    wait_for(lambda: admin.registry_calls == 2)
    service.stop(remove=True)
    wait_for(lambda: admin.remove_calls == 2)

    assert service._get_process_state().last_remove_requested_generation == 2


def test_new_start_cancels_pending_remove_before_worker_can_claim_it():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()
    service.stop(remove=True)
    pending = state.pending_remove
    assert pending is not None

    service.start()

    assert pending.done_event.is_set() is True
    assert state.pending_remove is None
    assert state.generation == 2
    admin.release.set()
    wait_for(lambda: admin.registry_calls >= 2)
    assert admin.remove_calls == 0
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_new_worker_waiting_for_active_remove_rechecks_after_stop():
    admin = BlockingRemoveAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=True)
    assert admin.remove_started.wait(timeout=1)

    service.start()
    assert state.generation == 2
    service.stop(remove=False)
    admin.remove_release.set()
    wait_for(lambda: not state.stopping_workers)

    assert admin.registry_calls == 1
    assert admin.remove_calls == 1


def test_failed_active_remove_still_wakes_current_new_worker():
    admin = BlockingRemoveAdmin(remove_success=False)
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=True)
    assert admin.remove_started.wait(timeout=1)

    service.start()
    admin.remove_release.set()

    wait_for(lambda: admin.registry_calls == 2)
    assert state.generation == 2
    assert state.registered is True
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_active_then_newer_pending_is_drained_by_its_own_worker():
    admin = FirstRemoveBlocksAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=True)
    assert admin.first_remove_started.wait(timeout=1)

    service.start()
    service.stop(remove=True)
    assert state.active_remove is not None
    assert state.active_remove.generation == 1
    assert state.pending_remove is not None
    assert state.pending_remove.generation == 2
    admin.first_remove_release.set()

    wait_for(lambda: admin.remove_calls == 2)
    wait_for(lambda: state.active_remove is None)
    assert state.pending_remove is None


def test_newer_start_can_cancel_newer_pending_while_old_active_runs():
    admin = FirstRemoveBlocksAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=True)
    assert admin.first_remove_started.wait(timeout=1)
    service.start()
    service.stop(remove=True)
    pending = state.pending_remove
    assert pending is not None and pending.generation == 2

    service.start()

    assert state.generation == 3
    assert pending.done_event.is_set() is True
    assert state.pending_remove is None
    admin.first_remove_release.set()
    wait_for(lambda: admin.registry_calls == 2)
    assert admin.remove_calls == 1
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_stopping_worker_claim_and_record_removal_are_atomic():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    ctx = _RegistryWorkerContext(3, threading.Event())
    operation = _RemoveOperation(3, threading.Event())
    state.generation = 3
    state.stopping_workers[3] = ctx
    state.pending_remove = operation

    service._finish_worker(state, ctx)

    assert 3 not in state.stopping_workers
    assert state.pending_remove is None
    assert state.active_remove is None
    assert operation.done_event.is_set() is True
    assert admin.remove_calls == 1


def test_other_generation_stopping_worker_does_not_block_cleanup_actor():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 2
    state.stopping_workers[1] = _RegistryWorkerContext(
        1, threading.Event()
    )
    operation = _RemoveOperation(2, threading.Event())
    state.pending_remove = operation

    service._schedule_pending_remove(state, raise_start_error=True)

    assert operation.done_event.wait(timeout=1)
    assert admin.remove_calls == 1
    assert 1 in state.stopping_workers


def test_cleanup_actor_that_cannot_claim_clears_its_association():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    pending = _RemoveOperation(2, threading.Event())
    other_active = _RemoveOperation(1, threading.Event())
    state.pending_remove = pending

    with state.state_lock:
        service._schedule_pending_remove(state, raise_start_error=True)
        first_actor = pending.thread
        state.active_remove = other_active

    wait_for(lambda: first_actor not in state.cleanup_actors)
    assert state.pending_remove is pending
    assert pending.thread is None

    with state.state_lock:
        state.active_remove = None
    service._schedule_pending_remove(state, raise_start_error=True)
    assert pending.done_event.wait(timeout=1)
    assert admin.remove_calls == 1


def test_scheduled_cleanup_actor_does_not_restore_cancelled_pending():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    pending = _RemoveOperation(1, threading.Event())
    state.pending_remove = pending

    with state.state_lock:
        service._schedule_pending_remove(state, raise_start_error=True)
        actor = pending.thread
        state.pending_remove = None
        pending.done_event.set()

    wait_for(lambda: actor not in state.cleanup_actors)
    assert pending.thread is None
    assert state.pending_remove is None
    assert admin.remove_calls == 0


def test_cleanup_thread_start_failure_terminates_operation(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    operation = _RemoveOperation(1, threading.Event())
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.pending_remove = operation
    failed_thread = mocker.Mock()
    failed_thread.start.side_effect = RuntimeError("cannot start cleanup")
    mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        return_value=failed_thread,
    )

    with pytest.raises(RuntimeError, match="cannot start cleanup"):
        service._schedule_pending_remove(state, raise_start_error=True)

    assert operation.done_event.is_set() is True
    assert operation.thread is None
    assert state.pending_remove is None
    assert state.active_remove is None
    assert not state.cleanup_actors
    assert state.last_remove_requested_generation == 1
    assert admin.remove_calls == 0


def test_public_stop_propagates_cleanup_start_failure_after_local_stop(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.generation = 1
    failed_thread = mocker.Mock()
    failed_thread.start.side_effect = RuntimeError("cleanup start failed")
    mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        return_value=failed_thread,
    )

    with pytest.raises(RuntimeError, match="cleanup start failed"):
        service.stop(remove=True)

    assert state.worker is None
    assert state.pending_remove is None
    assert state.active_remove is None
    assert state.last_remove_requested_generation == 1
    assert state.last_error is not None


def test_remove_completion_identity_guard_preserves_new_active():
    admin = BlockingRemoveAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    old = _RemoveOperation(1, threading.Event())
    new = _RemoveOperation(2, threading.Event())
    state.active_remove = old
    state.registered = True
    executor = threading.Thread(target=service._execute_remove, args=(state, old))
    executor.start()
    assert admin.remove_started.wait(timeout=1)

    with state.state_lock:
        state.active_remove = new
    admin.remove_release.set()
    executor.join(timeout=1)

    assert state.active_remove is new
    assert state.registered is True
    assert state.last_applied_rpc_sequence == 0
    assert old.done_event.is_set() is True


def test_remove_failure_is_accepted_ordered_and_preserves_registered():
    admin = FakeAdmin(remove_success=False)
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    operation = _RemoveOperation(1, threading.Event())
    state.active_remove = operation
    state.registered = True

    service._execute_remove(state, operation)

    assert state.registered is True
    assert state.last_registry_success is False
    assert state.last_applied_rpc_sequence == 1
    assert operation.done_event.is_set() is True


def test_stale_remove_completion_still_clears_own_active_and_finishes():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    operation = _RemoveOperation(1, threading.Event())
    state.active_remove = operation
    state.registered = True
    state.last_applied_rpc_sequence = 1

    service._execute_remove(state, operation)

    assert state.active_remove is None
    assert state.registered is True
    assert state.last_applied_rpc_sequence == 1
    assert operation.result is not None
    assert operation.result.success is True
    assert operation.done_event.is_set() is True


def test_first_explicit_register_in_live_generation_creates_coordination():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.generation = 1

    coordination, generation = service._join_register_coordination(state)

    assert generation == 1
    assert coordination is not None
    assert state.register_coordination is coordination
    assert coordination.generation == 1
    assert coordination.inflight_count == 1
    assert coordination.cleanup_requested is False
    assert coordination.done_event.is_set() is False


def test_register_coordination_event_is_set_only_after_reconcile(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    coordination, generation = service._join_register_coordination(state)
    assert coordination is not None
    with state.state_lock:
        assert service._request_remove_locked(state) is None
    original = service._reconcile_register_coordination_locked

    def reconcile(current_state, current_coordination):
        assert coordination.done_event.is_set() is False
        operation = original(current_state, current_coordination)
        assert current_state.pending_remove is operation
        return operation

    mocker.patch.object(
        service,
        "_reconcile_register_coordination_locked",
        side_effect=reconcile,
    )
    schedule = mocker.patch.object(service, "_schedule_pending_remove")

    service._commit_one_shot(
        state,
        CallResult(success=True, address="http://a:8080"),
        1,
        remove=False,
        generation=generation,
        coordination=coordination,
    )

    assert coordination.done_event.is_set() is True
    assert state.last_successfully_removed_generation is None
    assert state.last_remove_requested_generation == 1
    assert state.pending_remove is not None
    schedule.assert_called_once_with(state, raise_start_error=False)


def test_cleanup_linearization_closes_register_coordination_window():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    first, generation = service._join_register_coordination(state)
    assert first is not None

    with state.state_lock:
        service._request_remove_locked(state)
    second, second_generation = service._join_register_coordination(state)

    assert first.cleanup_requested is True
    assert first.inflight_count == 1
    assert second is None
    assert generation == second_generation == 1

    service._commit_one_shot(
        state,
        CallResult(success=False, error="failed"),
        1,
        remove=False,
        generation=generation,
        coordination=first,
    )
    assert first.done_event.is_set() is True
    assert state.register_coordination is None
    assert state.pending_remove is None


def test_failed_register_before_shutdown_still_cleans_existing_registration():
    admin = BlockingRegistryAdmin(result=False)
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.registered = True
    results = []
    caller = threading.Thread(
        target=lambda: results.append(service.register_once_result())
    )
    caller.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 1
    )

    service.shutdown(deregister_on_exit=True)

    coordination = state.register_coordination
    assert coordination is not None
    assert coordination.cleanup_requested is True
    assert state.pending_remove is None
    assert state.active_remove is None
    assert admin.remove_calls == 0

    admin.release.set()
    caller.join(timeout=1)
    assert not caller.is_alive()
    wait_for(lambda: admin.remove_calls == 1)
    wait_for(lambda: state.register_coordination is None)
    wait_for(lambda: not state.cleanup_actors)

    assert len(results) == 1
    assert results[0].success is False
    assert state.registered is False
    assert state.last_successfully_removed_generation == 1
    assert state.pending_remove is None
    assert state.active_remove is None


def test_failed_register_after_successful_cleanup_needs_no_new_remove():
    admin = BlockingRegistryAdmin(result=False)
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    cached = CallResult(success=True, address="http://a:8080")
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = cached
    results = []
    caller = threading.Thread(
        target=lambda: results.append(service.register_once_result())
    )
    caller.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 1
    )

    service.shutdown(deregister_on_exit=True)
    admin.release.set()
    caller.join(timeout=1)
    assert not caller.is_alive()
    wait_for(lambda: state.register_coordination is None)

    assert len(results) == 1
    assert results[0].success is False
    assert admin.remove_calls == 0
    assert state.last_successfully_removed_generation == 1
    assert state.last_successfully_removed_result is cached
    assert state.pending_remove is None
    assert state.active_remove is None


def test_eight_explicit_registers_before_shutdown_share_one_cleanup():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.registered = True
    results = []
    callers = [
        threading.Thread(
            target=lambda: results.append(service.register_once_result())
        )
        for _ in range(8)
    ]
    for caller in callers:
        caller.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 8
    )

    service.shutdown(deregister_on_exit=True)

    coordination = state.register_coordination
    assert coordination is not None
    assert coordination.cleanup_requested is True
    assert state.pending_remove is None
    assert state.active_remove is None
    assert admin.remove_calls == 0

    admin.release.set()
    for caller in callers:
        caller.join(timeout=2)
        assert not caller.is_alive()

    wait_for(lambda: admin.remove_calls == 1)
    wait_for(lambda: state.register_coordination is None)
    wait_for(lambda: not state.cleanup_actors)
    assert len(results) == 8
    assert all(result.success for result in results)
    assert admin.registry_calls == 8
    assert state.registered is False
    assert state.pending_remove is None
    assert state.active_remove is None


def test_newer_register_completion_keeps_pending_after_older_remove_rpc(
    mocker,
):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.registered = True
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    coordination = _RegisterCoordination(
        generation=1,
        inflight_count=1,
        cleanup_requested=True,
    )
    state.register_coordination = coordination
    active = _RemoveOperation(1, threading.Event())
    state.active_remove = active
    remove_rpc_finished = threading.Event()
    allow_remove_completion = threading.Event()
    original = service._complete_remove_operation

    def gated_completion(*args):
        remove_rpc_finished.set()
        allow_remove_completion.wait(timeout=2)
        return original(*args)

    mocker.patch.object(
        service, "_complete_remove_operation", side_effect=gated_completion
    )
    remover = threading.Thread(
        target=service._execute_remove, args=(state, active)
    )
    remover.start()
    assert remove_rpc_finished.wait(timeout=1)

    register_result, register_sequence = service._call_registry(
        state, remove=False
    )
    service._commit_one_shot(
        state,
        register_result,
        register_sequence,
        remove=False,
        generation=1,
        coordination=coordination,
    )

    fallback = state.pending_remove
    assert fallback is not None
    assert state.last_applied_rpc_sequence == 2
    assert state.registered is True
    assert coordination.done_event.is_set() is True
    allow_remove_completion.set()
    remover.join(timeout=1)

    assert not remover.is_alive()
    assert fallback.done_event.wait(timeout=1)
    wait_for(lambda: admin.remove_calls == 2)
    assert state.last_successfully_removed_generation == 1
    assert state.registered is False
    assert state.last_applied_rpc_sequence == 3


def test_newer_active_remove_cancels_register_fallback():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.registered = False
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    coordination = _RegisterCoordination(
        generation=1,
        inflight_count=1,
        cleanup_requested=True,
    )
    state.register_coordination = coordination
    active = _RemoveOperation(1, threading.Event())
    state.active_remove = active

    register_result, register_sequence = service._call_registry(
        state, remove=False
    )
    service._commit_one_shot(
        state,
        register_result,
        register_sequence,
        remove=False,
        generation=1,
        coordination=coordination,
    )
    fallback = state.pending_remove
    assert fallback is not None

    service._execute_remove(state, active)

    assert fallback.done_event.is_set() is True
    assert state.pending_remove is None
    assert state.last_successfully_removed_generation == 1
    assert state.registered is False
    assert admin.remove_calls == 1
    assert state.last_applied_rpc_sequence == 2


def test_all_failed_coordinated_registers_keep_successful_cleanup():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    first, generation = service._join_register_coordination(state)
    second, _ = service._join_register_coordination(state)
    assert first is second
    assert first is not None
    with state.state_lock:
        service._request_remove_locked(state)

    failure = CallResult(success=False, error="register failed")
    service._commit_one_shot(
        state,
        failure,
        1,
        remove=False,
        generation=generation,
        coordination=first,
    )
    service._commit_one_shot(
        state,
        failure,
        2,
        remove=False,
        generation=generation,
        coordination=second,
    )

    assert first.done_event.is_set() is True
    assert state.register_coordination is None
    assert state.last_successfully_removed_generation == 1
    assert state.pending_remove is None


def test_two_concurrent_registers_and_shutdown_converge_to_cleanup():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    results = []
    callers = [
        threading.Thread(
            target=lambda: results.append(service.register_once_result())
        )
        for _ in range(2)
    ]
    for caller in callers:
        caller.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 2
    )

    service.shutdown(deregister_on_exit=True)

    coordination = state.register_coordination
    assert coordination is not None
    assert coordination.cleanup_requested is True
    assert admin.remove_calls == 0
    admin.release.set()
    for caller in callers:
        caller.join(timeout=1)

    wait_for(lambda: state.last_successfully_removed_generation == 1)
    wait_for(lambda: state.register_coordination is None)
    assert len(results) == 2
    assert all(result.success for result in results)
    assert admin.registry_calls == 2
    assert 1 <= admin.remove_calls <= 2
    assert state.registered is False
    assert state.pending_remove is None
    assert state.active_remove is None


def test_two_failed_concurrent_registers_need_no_new_cleanup():
    admin = BlockingRegistryAdmin(result=False)
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    results = []
    callers = [
        threading.Thread(
            target=lambda: results.append(service.register_once_result())
        )
        for _ in range(2)
    ]
    for caller in callers:
        caller.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 2
    )
    service.shutdown(deregister_on_exit=True)
    admin.release.set()
    for caller in callers:
        caller.join(timeout=1)

    wait_for(lambda: state.register_coordination is None)
    assert len(results) == 2
    assert all(not result.success for result in results)
    assert state.last_successfully_removed_generation == 1
    assert admin.remove_calls == 0


def test_partially_successful_concurrent_registers_still_require_cleanup():
    admin = PartiallySuccessfulBlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    results = []
    callers = [
        threading.Thread(
            target=lambda: results.append(service.register_once_result())
        )
        for _ in range(2)
    ]
    for caller in callers:
        caller.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 2
    )

    service.shutdown(deregister_on_exit=True)
    admin.release.set()
    for caller in callers:
        caller.join(timeout=1)

    wait_for(lambda: state.last_successfully_removed_generation == 1)
    wait_for(lambda: state.register_coordination is None)
    assert len(results) == 2
    assert sorted(result.success for result in results) == [False, True]
    assert admin.registry_calls == 2
    assert admin.remove_calls >= 1
    assert state.registered is False
    assert state.pending_remove is None
    assert state.active_remove is None


def test_terminal_sync_remove_waits_for_open_register_coordination():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    state.last_successfully_removed_generation = 1
    state.last_successfully_removed_result = CallResult(success=True)
    register_results = []
    register = threading.Thread(
        target=lambda: register_results.append(
            service.register_once_result()
        )
    )
    register.start()
    assert admin.started.wait(timeout=1)
    wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 1
    )
    remove_results = []
    remover = threading.Thread(
        target=lambda: remove_results.append(service.remove_once_result())
    )
    remover.start()

    time.sleep(0.02)
    assert admin.remove_calls == 0
    admin.release.set()
    register.join(timeout=1)
    remover.join(timeout=1)

    assert register_results[0].success is True
    assert remove_results[0].success is True
    assert admin.registry_calls == 1
    assert admin.remove_calls == 1
    assert state.last_successfully_removed_generation == 1


def test_old_active_completion_is_accepted_before_new_generation_registry():
    admin = OldActiveNewGenerationAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    assert state.registered is True
    service.stop(remove=True)
    assert admin.remove_started.wait(timeout=1)
    old_operation = state.active_remove
    assert old_operation is not None

    service.start()
    assert state.generation == 2
    assert state.worker is not None
    admin.remove_release.set()
    assert admin.second_registry_started.wait(timeout=1)

    assert old_operation.done_event.is_set() is True
    assert old_operation.result is not None
    assert old_operation.result.success is True
    assert state.last_applied_rpc_sequence == 2
    assert state.registered is False
    assert state.last_successfully_removed_generation != 1

    admin.second_registry_release.set()
    wait_for(lambda: state.last_applied_rpc_sequence == 3)
    assert state.registered is True
    assert state.generation == 2
    service.stop()
    wait_for(lambda: not state.stopping_workers)


def test_old_generation_register_completion_updates_rpc_state_only():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.generation = 1
    old_coordination, captured_generation = (
        service._join_register_coordination(state)
    )
    assert old_coordination is not None

    new_coordination = _RegisterCoordination(generation=2)
    cached_result = CallResult(success=True, address="http://new:8080")
    pending = _RemoveOperation(2, threading.Event())
    with state.state_lock:
        state.generation = 2
        state.register_coordination = new_coordination
        state.last_remove_requested_generation = 2
        state.last_successfully_removed_generation = 2
        state.last_successfully_removed_result = cached_result
        state.pending_remove = pending
        state.rpc_sequence = 1

    result = CallResult(
        success=True,
        msg="generation one register completed",
        address="http://a:8080",
    )
    service._commit_one_shot(
        state,
        result,
        1,
        remove=False,
        generation=captured_generation,
        coordination=old_coordination,
    )

    assert state.last_applied_rpc_sequence == 1
    assert state.registered is True
    assert state.last_registry_message == result.message
    assert state.generation == 2
    assert state.register_coordination is new_coordination
    assert state.last_remove_requested_generation == 2
    assert state.last_successfully_removed_generation == 2
    assert state.last_successfully_removed_result is cached_result
    assert state.pending_remove is pending
    assert old_coordination.inflight_count == 0
    assert old_coordination.done_event.is_set() is True


def test_sequence_is_allocated_only_after_network_lock_is_acquired():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    state.network_lock.acquire()
    caller = threading.Thread(target=service.register_once_result)
    caller.start()

    time.sleep(0.02)
    assert state.rpc_sequence == 0
    assert admin.registry_calls == 0
    state.network_lock.release()
    caller.join(timeout=1)

    assert state.rpc_sequence == 1
    assert state.last_applied_rpc_sequence == 1


def test_equal_sequence_is_rejected_and_only_strictly_newer_is_accepted():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    state.last_applied_rpc_sequence = 5
    state.registered = False
    state.last_registry_message = "kept"
    result = CallResult(success=True, msg="new")

    service._commit_one_shot(state, result, 5, remove=False)

    assert state.registered is False
    assert state.last_registry_message == "kept"
    assert state.last_applied_rpc_sequence == 5

    service._commit_one_shot(state, result, 6, remove=False)
    assert state.registered is True
    assert state.last_registry_message == "new"
    assert state.last_applied_rpc_sequence == 6


def test_newer_failure_prevents_older_success_from_overwriting_snapshot():
    service = RegistryService(make_config(), FakeAdmin())
    state = service._get_process_state()
    newer_failure = CallResult(
        success=False, error="new failure", error_type="network"
    )
    older_success = CallResult(success=True, msg="old success")

    service._commit_one_shot(state, newer_failure, 2, remove=False)
    service._commit_one_shot(state, older_success, 1, remove=False)

    assert state.registered is False
    assert state.last_registry_message == "new failure"
    assert state.last_applied_rpc_sequence == 2


def test_network_lock_serializes_worker_registry_and_sync_remove():
    admin = BlockingRegistryAdmin()
    service = RegistryService(make_config(), admin)
    service.start()
    assert admin.started.wait(timeout=1)
    result = []
    caller = threading.Thread(
        target=lambda: result.append(service.remove_once_result())
    )
    caller.start()

    time.sleep(0.02)
    assert admin.remove_calls == 0
    admin.release.set()
    caller.join(timeout=1)

    assert admin.remove_calls == 1
    assert result[0].success is True
    service.stop()
    wait_for(lambda: not service._get_process_state().stopping_workers)


def test_network_lock_serializes_background_remove_and_sync_register():
    admin = BlockingRemoveAdmin()
    service = RegistryService(make_config(), admin)
    state = service._get_process_state()
    operation = _RemoveOperation(1, threading.Event())
    state.active_remove = operation
    cleanup = threading.Thread(
        target=service._execute_remove, args=(state, operation)
    )
    cleanup.start()
    assert admin.remove_started.wait(timeout=1)
    result = []
    caller = threading.Thread(
        target=lambda: result.append(service.register_once_result())
    )
    caller.start()

    time.sleep(0.02)
    assert admin.registry_calls == 0
    admin.remove_release.set()
    cleanup.join(timeout=1)
    caller.join(timeout=1)

    assert admin.registry_calls == 1
    assert result[0].success is True
    assert state.last_applied_rpc_sequence == 2


class PoisonLock:
    def __enter__(self):
        raise AssertionError("inherited state lock was acquired")

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_fork_status_and_running_replace_state_without_parent_lock(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    parent = service._process_state
    parent.registered = True
    parent.generation = 9
    parent.worker = _RegistryWorkerContext(9, threading.Event())
    parent.state_lock = PoisonLock()
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=parent.pid + 1,
    )

    snapshot = service.status_snapshot()

    child = service._process_state
    assert child is not parent
    assert child.pid == parent.pid + 1
    assert snapshot["registered"] is False
    assert snapshot["registry_thread_running"] is False
    assert child.generation == 0
    assert service.is_running is False


def test_fork_stale_remove_finishes_operation_without_parent_lock(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    parent = service._process_state
    operation = _RemoveOperation(1, threading.Event())
    parent.active_remove = operation
    parent.state_lock = PoisonLock()
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=parent.pid + 1,
    )

    service._execute_remove(parent, operation)

    assert service._process_state is not parent
    assert operation.result is not None
    assert operation.result.success is False
    assert operation.done_event.is_set() is True


def test_fork_stale_cleanup_actor_finishes_operation_without_parent_lock(
    mocker,
):
    service = RegistryService(make_config(), FakeAdmin())
    parent = service._process_state
    operation = _RemoveOperation(1, threading.Event())
    parent.pending_remove = operation
    parent.state_lock = PoisonLock()
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=parent.pid + 1,
    )

    service._run_cleanup_actor(parent, operation)

    assert service._process_state is not parent
    assert operation.result is not None
    assert operation.result.success is False
    assert operation.done_event.is_set() is True


@pytest.mark.parametrize("method_name", ["register_once_result", "remove_once_result"])
def test_fork_disabled_snapshot_uses_blank_child_state(
    mocker, method_name
):
    config = make_config(XXL_JOB_ENABLED=False)
    admin = FakeAdmin()
    service = RegistryService(config, admin)
    parent = service._process_state
    parent.registered = True
    parent.generation = 4
    parent.state_lock = PoisonLock()
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=parent.pid + 1,
    )

    result = getattr(service, method_name)()

    child = service._process_state
    assert child is not parent
    assert result.error == "Flask-XXLJob is disabled."
    assert child.registered is False
    assert child.generation == 0
    assert child.rpc_sequence == 0
    assert child.last_applied_rpc_sequence == 0
    assert child.last_error == result
    assert admin.registry_calls == admin.remove_calls == 0


def test_fork_finalizer_uses_only_blank_child_state(mocker):
    closed = mocker.Mock()
    service = RegistryService(make_config(), FakeAdmin(), close_logs=closed)
    parent = service._process_state
    inherited_event = mocker.Mock()
    parent.worker = _RegistryWorkerContext(1, inherited_event)
    inherited_activate_event = mocker.Mock()
    inherited_prepared_stop = mocker.Mock()
    prepared_context = _RegistryWorkerContext(2, inherited_prepared_stop)
    parent.prepared_start = _PreparedRegistryStart(
        state=parent,
        context=prepared_context,
        activate_event=inherited_activate_event,
        thread=mocker.Mock(),
    )
    parent.generation = 1
    parent.state_lock = PoisonLock()
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=parent.pid + 1,
    )

    service.shutdown(deregister_on_exit=True)

    child = service._process_state
    inherited_event.set.assert_not_called()
    inherited_prepared_stop.set.assert_not_called()
    inherited_activate_event.set.assert_not_called()
    assert child.generation == 0
    assert child.logs_closed is True
    closed.assert_called_once_with()


def test_finalizer_generation_zero_skips_validation_and_remove(mocker):
    config = make_config()
    validate = mocker.patch.object(config, "validate_registry")
    admin = FakeAdmin()
    closed = mocker.Mock()
    service = RegistryService(config, admin, close_logs=closed)

    service.shutdown(deregister_on_exit=True)

    validate.assert_not_called()
    assert admin.remove_calls == 0
    closed.assert_called_once_with()


def test_sync_registration_does_not_create_finalizer_remove_eligibility(mocker):
    config = make_config()
    admin = FakeAdmin()
    service = RegistryService(config, admin, close_logs=mocker.Mock())
    service.register_once_result()

    service.shutdown(deregister_on_exit=True)

    assert service._get_process_state().generation == 0
    assert admin.remove_calls == 0


def test_finalizer_does_not_validate_or_repeat_used_generation(mocker):
    config = make_config()
    admin = FakeAdmin()
    service = RegistryService(config, admin, close_logs=mocker.Mock())
    state = service._get_process_state()
    state.generation = 1
    state.last_remove_requested_generation = 1
    validate = mocker.patch.object(config, "validate_registry")

    service.shutdown(deregister_on_exit=True)

    validate.assert_not_called()
    assert admin.remove_calls == 0


def test_finalizer_can_request_unused_remove_after_plain_stop(mocker):
    config = make_config()
    admin = FakeAdmin()
    service = RegistryService(config, admin, close_logs=mocker.Mock())
    service.start()
    wait_for(lambda: admin.registry_calls == 1)
    state = service._get_process_state()
    service.stop(remove=False)
    wait_for(lambda: not state.stopping_workers)

    service.shutdown(deregister_on_exit=True)

    wait_for(lambda: admin.remove_calls == 1)
    assert state.last_remove_requested_generation == 1


def test_finalizer_invalid_remove_config_still_stops_locally(mocker):
    config = make_config()
    admin = BlockingRegistryAdmin()
    closed = mocker.Mock()
    service = RegistryService(config, admin, close_logs=closed)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()
    ctx = state.worker
    config.admin_addresses = []

    service.shutdown(deregister_on_exit=True)

    assert state.worker is None
    assert state.stopping_workers[1] is ctx
    assert ctx.stop_event.is_set() is True
    assert admin.remove_calls == 0
    admin.release.set()
    wait_for(lambda: not state.stopping_workers)
    closed.assert_called_once_with()


def test_finalizer_swallows_cleanup_start_failure_and_closes_logs(mocker):
    closed = mocker.Mock()
    service = RegistryService(make_config(), FakeAdmin(), close_logs=closed)
    state = service._get_process_state()
    state.generation = 1
    failed_thread = mocker.Mock()
    failed_thread.start.side_effect = RuntimeError("cleanup start failed")
    mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        return_value=failed_thread,
    )

    service.shutdown(deregister_on_exit=True)

    assert state.last_remove_requested_generation == 1
    assert state.pending_remove is None
    assert state.active_remove is None
    assert state.logs_closed is True
    closed.assert_called_once_with()


def test_logs_close_once_immediately_when_idle(mocker):
    closed = mocker.Mock()
    service = RegistryService(make_config(), FakeAdmin(), close_logs=closed)

    service.shutdown(deregister_on_exit=False)
    service.shutdown(deregister_on_exit=False)

    closed.assert_called_once_with()
    assert service._get_process_state().logs_closed is True


def test_actual_log_close_runs_outside_state_lock():
    class TrackingStateLock:
        def __init__(self):
            self._lock = threading.RLock()
            self.depth = 0

        def __enter__(self):
            self._lock.acquire()
            self.depth += 1
            return self

        def __exit__(self, exc_type, exc, traceback):
            self.depth -= 1
            self._lock.release()
            return False

    lock = TrackingStateLock()
    observed_depths = []
    service = RegistryService(
        make_config(),
        FakeAdmin(),
        close_logs=lambda: observed_depths.append(lock.depth),
    )
    state = service._get_process_state()
    state.state_lock = lock

    service.shutdown(deregister_on_exit=False)

    assert observed_depths == [0]
    assert state.logs_closed is True


def test_logs_close_only_after_last_background_worker_exits(mocker):
    admin = BlockingRegistryAdmin()
    closed = mocker.Mock()
    service = RegistryService(make_config(), admin, close_logs=closed)
    service.start()
    assert admin.started.wait(timeout=1)
    state = service._get_process_state()

    service.shutdown(deregister_on_exit=False)

    closed.assert_not_called()
    admin.release.set()
    wait_for(lambda: state.logs_closed)
    closed.assert_called_once_with()
    assert admin.remove_calls == 0


def test_logs_close_only_after_background_remove_actor_exits(mocker):
    admin = BlockingRemoveAdmin()
    closed = mocker.Mock()
    service = RegistryService(make_config(), admin, close_logs=closed)
    state = service._get_process_state()
    state.generation = 1

    service.shutdown(deregister_on_exit=True)

    assert admin.remove_started.wait(timeout=1)
    closed.assert_not_called()
    admin.remove_release.set()
    wait_for(lambda: state.logs_closed)
    closed.assert_called_once_with()

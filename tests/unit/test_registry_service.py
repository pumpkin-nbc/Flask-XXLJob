"""Registry service tests."""

from __future__ import annotations

import threading

import pytest

from flask_xxljob.client import CallResult
from flask_xxljob.config import XXLJobConfig
from flask_xxljob.registry.registry_service import RegistryService


def make_config(**overrides):
    mapping = {
        "XXL_JOB_ADMIN_ADDRESSES": ["http://a:8080"],
        "XXL_JOB_EXECUTOR_APP_NAME": "app",
        "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
        "XXL_JOB_REGISTRY_INTERVAL": 1,
    }
    mapping.update(overrides)
    return XXLJobConfig.from_mapping(mapping)


class FakeAdmin:
    def __init__(self, success=True):
        self.success = success
        self.registry_calls = 0
        self.remove_calls = 0

    def registry(self, request):
        self.registry_calls += 1
        return CallResult(success=self.success, address="http://a:8080")

    def registry_remove(self, request):
        self.remove_calls += 1
        return CallResult(success=self.success, address="http://a:8080")


class BlockingAdmin(FakeAdmin):
    def __init__(self):
        super().__init__()
        self.registry_started = threading.Event()
        self.registry_release = threading.Event()
        self.remove_started = threading.Event()
        self.registry_in_progress = False
        self.calls_overlapped = False

    def registry(self, request):
        self.registry_calls += 1
        self.registry_in_progress = True
        self.registry_started.set()
        self.registry_release.wait(timeout=5)
        self.registry_in_progress = False
        return CallResult(success=True, address="http://a:8080")

    def registry_remove(self, request):
        self.remove_calls += 1
        self.calls_overlapped = self.registry_in_progress
        self.remove_started.set()
        return CallResult(success=True, address="http://a:8080")


class FailingRemoveAdmin(FakeAdmin):
    def registry_remove(self, request):
        self.remove_calls += 1
        return CallResult(
            success=False,
            address="http://a:8080",
            error="remove failed",
            error_type="business",
        )


class RaisingRemoveAdmin(FakeAdmin):
    def registry_remove(self, request):
        self.remove_calls += 1
        raise RuntimeError("remove exploded")


def test_register_once_result():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    result = service.register_once_result()
    assert result.success is True
    assert admin.registry_calls == 1


def test_remove_once_result():
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    assert service.remove_once_result().success is True
    assert admin.remove_calls == 1


def test_register_failure_does_not_raise():
    admin = FakeAdmin(success=False)
    service = RegistryService(make_config(), admin)
    result = service.register_once_result()
    assert result.success is False


def test_start_is_idempotent():
    admin = FakeAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=3600), admin)
    service.start()
    service.start()
    assert service.is_running is True
    service.stop(remove=False)
    assert service.is_running is False


def test_stop_triggers_remove():
    admin = FakeAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=3600), admin)
    service.start()
    service.stop(remove=True)
    assert admin.remove_calls == 1


def test_stop_defers_remove_until_blocked_renewal_finishes():
    admin = BlockingAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=1), admin)
    service.start()
    assert admin.registry_started.wait(timeout=1)

    service.stop(remove=True)

    assert admin.remove_calls == 0
    assert service.is_running is True
    assert service.status_snapshot()["registry_thread_running"] is True

    admin.registry_release.set()
    assert admin.remove_started.wait(timeout=1)
    assert admin.calls_overlapped is False
    assert admin.remove_calls == 1

    # A later stop only waits for cleanup; it must not deregister again.
    service.stop(remove=False)
    assert service.is_running is False
    assert admin.remove_calls == 1


def test_pid_change_resets_all_process_local_state(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    inherited_thread = mocker.Mock()
    inherited_thread.is_alive.return_value = True
    service._thread = inherited_thread
    old_event = service._stop_event
    old_lock = service._lock
    old_call_lock = service._call_lock
    old_status_lock = service._status_lock
    service._remove_requested = True
    service._remove_claimed = True
    service._shutdown_callbacks = [mocker.Mock()]
    service._registered = True
    service._last_registry_time = "parent-time"
    service._last_registry_success = True
    service._last_registry_admin_address = "http://parent:8080"
    service._last_registry_error_type = "parent-error"
    service._last_registry_message = "parent-message"
    child_pid = service._pid + 1
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=child_pid,
    )

    snapshot = service.status_snapshot()

    assert service._pid == child_pid
    assert service._thread is None
    assert service._stop_event is not old_event
    assert service._lock is not old_lock
    assert service._call_lock is not old_call_lock
    assert service._status_lock is not old_status_lock
    assert service._remove_requested is False
    assert service._remove_claimed is False
    assert service._shutdown_callbacks == []
    assert snapshot == {
        "registered": False,
        "last_registry_time": None,
        "last_registry_success": None,
        "last_registry_admin_address": None,
        "last_registry_error_type": None,
        "last_registry_message": None,
        "registry_thread_running": False,
    }
    inherited_thread.is_alive.assert_not_called()


def test_start_after_pid_change_uses_a_new_daemon_thread(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    inherited_thread = mocker.Mock()
    inherited_thread.is_alive.return_value = True
    service._thread = inherited_thread
    child_thread = mocker.Mock()
    child_thread.is_alive.return_value = True
    thread_factory = mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        return_value=child_thread,
    )
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=service._pid + 1,
    )

    service.start()

    assert service._thread is child_thread
    child_thread.start.assert_called_once_with()
    thread_factory.assert_called_once_with(
        target=service._run_loop,
        name="flask-xxljob-registry",
        daemon=True,
    )
    inherited_thread.is_alive.assert_not_called()


def test_stop_after_pid_change_never_joins_inherited_thread(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    inherited_thread = mocker.Mock()
    inherited_thread.is_alive.return_value = True
    service._thread = inherited_thread
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=service._pid + 1,
    )

    service.stop(remove=False)

    inherited_thread.is_alive.assert_not_called()
    inherited_thread.join.assert_not_called()
    assert admin.remove_calls == 0


def test_is_running_resets_inherited_thread_after_pid_change(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    inherited_thread = mocker.Mock()
    inherited_thread.is_alive.return_value = True
    service._thread = inherited_thread
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        return_value=service._pid + 1,
    )

    assert service.is_running is False
    inherited_thread.is_alive.assert_not_called()


def test_thread_start_failure_restores_retryable_state(mocker):
    service = RegistryService(make_config(), FakeAdmin())
    failed_thread = mocker.Mock()
    failed_thread.start.side_effect = RuntimeError("cannot start")
    retry_thread = mocker.Mock()
    retry_thread.is_alive.return_value = True
    mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread",
        side_effect=[failed_thread, retry_thread],
    )

    with pytest.raises(RuntimeError, match="cannot start"):
        service.start()

    assert service._thread is None
    service.start()
    assert service._thread is retry_thread
    retry_thread.start.assert_called_once_with()


def test_register_and_remove_rebuild_call_lock_after_pid_change(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    parent_lock = service._call_lock
    current_pid = [service._pid + 1]
    mocker.patch(
        "flask_xxljob.registry.registry_service.os.getpid",
        side_effect=lambda: current_pid[0],
    )

    assert service.register_once_result().success is True
    child_lock = service._call_lock
    assert child_lock is not parent_lock
    assert service.status_snapshot()["registered"] is True

    current_pid[0] += 1
    assert service.remove_once_result().success is True
    assert service._call_lock is not child_lock
    assert service.status_snapshot()["registered"] is False
    assert admin.registry_calls == 1
    assert admin.remove_calls == 1


def test_status_snapshot_has_no_admin_or_thread_side_effects(mocker):
    admin = FakeAdmin()
    service = RegistryService(make_config(), admin)
    thread_factory = mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread"
    )

    snapshot = service.status_snapshot()

    assert snapshot["registered"] is False
    assert admin.registry_calls == 0
    assert admin.remove_calls == 0
    thread_factory.assert_not_called()


def test_deferred_shutdown_callback_runs_after_removal():
    admin = BlockingAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=1), admin)
    closed = threading.Event()
    service.start()
    assert admin.registry_started.wait(timeout=1)

    service.stop(remove=True, on_stopped=closed.set)

    assert closed.is_set() is False
    assert admin.remove_calls == 0
    admin.registry_release.set()
    assert admin.remove_started.wait(timeout=1)
    assert closed.wait(timeout=1)
    assert admin.remove_calls == 1


def test_repeated_stop_deregisters_at_most_once():
    admin = FakeAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=3600), admin)
    service.start()

    service.stop(remove=True)
    service.stop(remove=True)

    assert admin.remove_calls == 1


def test_stop_without_remove_does_not_deregister():
    admin = FakeAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=3600), admin)
    service.start()

    service.stop(remove=False)
    service.stop(remove=False)

    assert admin.remove_calls == 0


def test_remove_failure_is_kept_in_status_snapshot():
    admin = FailingRemoveAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=3600), admin)
    service.start()

    service.stop(remove=True)

    snapshot = service.status_snapshot()
    assert snapshot["registered"] is True
    assert snapshot["last_registry_success"] is False
    assert snapshot["last_registry_error_type"] == "business"
    assert snapshot["last_registry_message"] == "remove failed"


def test_unexpected_remove_exception_is_kept_in_status_snapshot():
    admin = RaisingRemoveAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=3600), admin)
    service.start()

    service.stop(remove=True)

    snapshot = service.status_snapshot()
    assert snapshot["registered"] is True
    assert snapshot["last_registry_success"] is False
    assert snapshot["last_registry_error_type"] == "RuntimeError"
    assert snapshot["last_registry_message"] == (
        "Unexpected error during XXL-JOB executor removal."
    )

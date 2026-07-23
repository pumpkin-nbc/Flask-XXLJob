"""Registry service tests."""

from __future__ import annotations

import threading

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

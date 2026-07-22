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

    def registry(self, request):
        self.registry_calls += 1
        self.registry_started.set()
        self.registry_release.wait(timeout=5)
        return CallResult(success=True, address="http://a:8080")

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


def test_stop_skips_remove_while_renewal_is_still_running():
    admin = BlockingAdmin()
    service = RegistryService(make_config(XXL_JOB_REGISTRY_INTERVAL=1), admin)
    service.start()
    assert admin.registry_started.wait(timeout=1)

    service.stop(remove=True)

    assert admin.remove_calls == 0
    assert service.is_running is True
    assert service.status_snapshot()["registry_thread_running"] is True

    admin.registry_release.set()
    service.stop(remove=False)
    assert service.is_running is False

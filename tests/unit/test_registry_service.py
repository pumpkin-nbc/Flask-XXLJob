"""Registry service tests."""

from __future__ import annotations

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

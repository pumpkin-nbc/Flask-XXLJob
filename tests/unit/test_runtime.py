"""Per-process XXLJobRuntime lifecycle tests."""

from __future__ import annotations

import pytest

from flask_xxljob.config import XXLJobConfig
from flask_xxljob.runtime import XXLJobRuntime


def make_runtime(mocker, **overrides):
    mapping = {
        "XXL_JOB_ADMIN_ADDRESSES": ["http://admin:8080/xxl-job-admin"],
        "XXL_JOB_EXECUTOR_APP_NAME": "runtime-app",
        "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
        "XXL_JOB_AUTO_REGISTER": False,
    }
    mapping.update(overrides)
    config = XXLJobConfig.from_mapping(mapping)
    registry_service = mocker.Mock()
    registry_service.status_snapshot.return_value = {
        "registered": False,
        "registry_thread_running": False,
    }
    logger = mocker.Mock()
    log_manager = mocker.Mock()
    log_manager.get_logger.return_value = logger
    runtime = XXLJobRuntime(
        config=config,
        callback_registry=mocker.Mock(),
        admin_client=mocker.Mock(),
        callback_client=mocker.Mock(),
        registry_service=registry_service,
        log_manager=log_manager,
    )
    return runtime, registry_service, log_manager


@pytest.mark.parametrize(
    "enabled,deregister_on_exit,registered,running,expected_remove",
    [
        (True, True, True, False, True),
        (True, True, False, True, True),
        (True, True, False, False, False),
        (True, False, True, True, False),
        (False, True, True, True, False),
    ],
)
def test_close_applies_exit_deregistration_policy(
    mocker,
    enabled,
    deregister_on_exit,
    registered,
    running,
    expected_remove,
):
    runtime, service, _ = make_runtime(
        mocker,
        XXL_JOB_ENABLED=enabled,
        XXL_JOB_DEREGISTER_ON_EXIT=deregister_on_exit,
    )
    service.status_snapshot.return_value = {
        "registered": registered,
        "registry_thread_running": running,
    }

    runtime.close()
    runtime.close()

    service.stop.assert_called_once()
    _, kwargs = service.stop.call_args
    assert kwargs["remove"] is expected_remove
    assert kwargs["on_stopped"] == runtime._finish_close


def test_close_resets_runtime_cleanup_state_after_pid_change(mocker):
    runtime, service, _ = make_runtime(mocker)
    old_lock = runtime._close_lock
    runtime._closed = True
    child_pid = runtime._pid + 1
    mocker.patch("flask_xxljob.runtime.os.getpid", return_value=child_pid)

    runtime.close()

    assert runtime._pid == child_pid
    assert runtime._close_lock is not old_lock
    assert runtime._closed is True
    service.stop.assert_called_once()

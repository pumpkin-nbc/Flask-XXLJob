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
    return runtime, registry_service, log_manager, logger


@pytest.mark.parametrize("deregister_on_exit", [False, True])
def test_close_delegates_nonblocking_shutdown_once(mocker, deregister_on_exit):
    runtime, service, log_manager, _ = make_runtime(
        mocker,
        XXL_JOB_DEREGISTER_ON_EXIT=deregister_on_exit,
    )

    runtime.close()
    runtime.close()

    log_manager.prepare_shutdown.assert_called_once_with()
    service.shutdown.assert_called_once_with(
        deregister_on_exit=deregister_on_exit
    )
    log_manager.close.assert_not_called()


def test_close_logs_shutdown_error_without_raising(mocker):
    runtime, service, _, logger = make_runtime(mocker)
    service.shutdown.side_effect = RuntimeError("shutdown")

    runtime.close()

    logger.exception.assert_called_once()


def test_close_resets_runtime_cleanup_state_after_pid_change(mocker):
    runtime, service, _, _ = make_runtime(mocker)
    old_lock = runtime._close_lock
    runtime._closed = True
    child_pid = runtime._pid + 1
    mocker.patch("flask_xxljob.runtime.os.getpid", return_value=child_pid)

    runtime.close()

    assert runtime._pid == child_pid
    assert runtime._close_lock is not old_lock
    assert runtime._closed is True
    service.shutdown.assert_called_once_with(deregister_on_exit=False)

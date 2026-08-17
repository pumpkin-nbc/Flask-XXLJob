"""Internal application and registry lifecycle helper tests."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob
from flask_xxljob._app import ApplicationRegistry
from flask_xxljob._lifecycle import (
    install_runtime_finalizer,
    safe_close_runtime,
    safe_stop_registry,
    start_registry_with_shutdown,
)


def test_application_registry_explicit_app_wins():
    registry = ApplicationRegistry()
    explicit = Flask("explicit")
    assert registry.resolve(explicit) is explicit


@pytest.mark.parametrize(
    "auto_register,auto_register_on_init,expected_calls",
    [
        (True, True, 1),
        (True, False, 0),
        (False, True, 0),
        (False, False, 0),
    ],
)
def test_init_app_registry_start_matrix(
    mocker, auto_register, auto_register_on_init, expected_calls
):
    start = mocker.patch(
        "flask_xxljob.extension.start_registry_with_shutdown"
    )
    app = Flask(
        "lifecycle-{}-{}".format(auto_register, auto_register_on_init)
    )
    app.config.update(
        XXL_JOB_ENABLED=True,
        XXL_JOB_AUTO_REGISTER=auto_register,
        XXL_JOB_AUTO_REGISTER_ON_INIT=auto_register_on_init,
        XXL_JOB_ADMIN_ADDRESSES=["http://admin:8080/xxl-job-admin"],
        XXL_JOB_EXECUTOR_APP_NAME="lifecycle-app",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )

    FlaskXXLJob(app)

    assert start.call_count == expected_calls
    app.extensions["xxljob"].close()


def test_auto_register_on_init_defaults_to_enabled(mocker):
    start = mocker.patch(
        "flask_xxljob.extension.start_registry_with_shutdown"
    )
    app = Flask("lifecycle-default")
    app.config.update(
        XXL_JOB_ENABLED=True,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_ADMIN_ADDRESSES=["http://admin:8080/xxl-job-admin"],
        XXL_JOB_EXECUTOR_APP_NAME="lifecycle-app",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )

    FlaskXXLJob(app)

    start.assert_called_once()
    app.extensions["xxljob"].close()


def test_delayed_registry_can_be_started_explicitly(mocker):
    app = Flask("lifecycle-delayed")
    app.config.update(
        XXL_JOB_ENABLED=True,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_AUTO_REGISTER_ON_INIT=False,
        XXL_JOB_ADMIN_ADDRESSES=["http://admin:8080/xxl-job-admin"],
        XXL_JOB_EXECUTOR_APP_NAME="lifecycle-app",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )
    extension = FlaskXXLJob(app)
    service = app.extensions["xxljob"].registry_service
    start = mocker.patch.object(service, "start")

    extension.start_registry(app)

    start.assert_called_once_with()
    app.extensions["xxljob"].close()


def test_start_registry_starts_service(mocker):
    service = mocker.Mock()

    start_registry_with_shutdown(service)

    service.start.assert_called_once_with()


def test_install_runtime_finalizer_uses_app_lifetime(mocker):
    app = Flask("lifecycle")
    runtime = mocker.Mock()
    finalize = mocker.patch("flask_xxljob._lifecycle.weakref.finalize")

    result = install_runtime_finalizer(app, runtime)

    finalize.assert_called_once_with(app, safe_close_runtime, runtime)
    assert result is finalize.return_value


def test_safe_close_runtime_swallows_shutdown_errors(mocker):
    runtime = mocker.Mock()
    runtime.close.side_effect = RuntimeError("shutdown")

    safe_close_runtime(runtime)

    runtime.close.assert_called_once_with()


def test_safe_stop_registry_swallows_shutdown_errors(mocker):
    service = mocker.Mock()
    service.stop.side_effect = RuntimeError("shutdown")

    safe_stop_registry(service)

    service.stop.assert_called_once_with()

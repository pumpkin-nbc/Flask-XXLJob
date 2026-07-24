"""Internal application and registry lifecycle helper tests."""

from __future__ import annotations

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


def test_init_app_starts_registry_when_enabled_and_auto_register(mocker):
    start = mocker.patch(
        "flask_xxljob.extension.start_registry_with_shutdown"
    )
    app = Flask("lifecycle-auto")
    app.debug = True
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


def test_init_app_skips_registry_when_auto_register_disabled(mocker):
    start = mocker.patch(
        "flask_xxljob.extension.start_registry_with_shutdown"
    )
    app = Flask("lifecycle-manual")
    app.debug = False
    app.config.update(
        XXL_JOB_ENABLED=True,
        XXL_JOB_AUTO_REGISTER=False,
    )

    FlaskXXLJob(app)

    start.assert_not_called()
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

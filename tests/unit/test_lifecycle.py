"""Internal application and Runtime finalizer lifecycle tests."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob
from flask_xxljob._app import ApplicationRegistry
from flask_xxljob._lifecycle import install_runtime_finalizer, safe_close_runtime
from flask_xxljob.exceptions import XXLJobConfigError


def configured_app(name, **overrides):
    app = Flask(name)
    app.config.update(
        XXL_JOB_ADMIN_ADDRESSES=["http://admin:8080/xxl-job-admin"],
        XXL_JOB_EXECUTOR_APP_NAME="lifecycle-app",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
        XXL_JOB_AUTO_REGISTER=False,
    )
    app.config.update(overrides)
    return app


def test_application_registry_explicit_app_wins():
    registry = ApplicationRegistry()
    explicit = Flask("explicit")
    assert registry.resolve(explicit) is explicit


@pytest.mark.parametrize(
    "enabled,auto_register,expected_calls",
    [
        (True, True, 1),
        (True, False, 0),
        (False, True, 0),
        (False, False, 0),
    ],
)
def test_init_app_auto_start_uses_public_start_registry(
    mocker, enabled, auto_register, expected_calls
):
    start = mocker.patch.object(FlaskXXLJob, "start_registry")
    app = configured_app(
        "lifecycle-{}-{}".format(enabled, auto_register),
        XXL_JOB_ENABLED=enabled,
        XXL_JOB_AUTO_REGISTER=auto_register,
    )

    FlaskXXLJob(app)

    assert start.call_count == expected_calls
    if expected_calls:
        start.assert_called_once_with(app)
    app.extensions["xxljob"].close()


def test_disabled_init_without_registry_configuration_has_no_side_effects(mocker):
    start = mocker.patch.object(FlaskXXLJob, "start_registry")
    app = Flask("disabled-protocol-only")
    app.config.update(
        XXL_JOB_ENABLED=False,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_ADMIN_ADDRESSES=[],
    )

    extension = FlaskXXLJob(app)

    start.assert_not_called()
    service = app.extensions["xxljob"].registry_service
    assert service.is_running is False
    extension.start_registry(app)
    assert service.is_running is False
    app.extensions["xxljob"].close()


def test_enabled_protocol_only_init_does_not_require_registry_configuration():
    app = Flask("enabled-protocol-only")
    app.config.update(
        XXL_JOB_ENABLED=True,
        XXL_JOB_AUTO_REGISTER=False,
        XXL_JOB_ADMIN_ADDRESSES=[],
        XXL_JOB_EXECUTOR_ADDRESS="",
    )

    extension = FlaskXXLJob(app)

    assert extension.get_status(app).registry_thread_running is False
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert {"/beat", "/idleBeat", "/run", "/kill", "/log"} <= rules
    app.extensions["xxljob"].close()


@pytest.mark.parametrize("removed_value", [False, True, "false"])
def test_removed_config_precedes_disabled_registry_short_circuit(removed_value):
    app = Flask("disabled-removed-{}".format(removed_value))
    app.config.update(
        XXL_JOB_ENABLED=False,
        XXL_JOB_AUTO_REGISTER_ON_INIT=removed_value,
    )

    with pytest.raises(XXLJobConfigError, match="已删除"):
        FlaskXXLJob(app)


def test_delayed_registry_can_be_started_explicitly(mocker):
    app = configured_app("lifecycle-delayed", XXL_JOB_AUTO_REGISTER=False)
    extension = FlaskXXLJob(app)
    service = app.extensions["xxljob"].registry_service
    start = mocker.patch.object(service, "start")

    extension.start_registry(app)

    start.assert_called_once_with()
    app.extensions["xxljob"].close()


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

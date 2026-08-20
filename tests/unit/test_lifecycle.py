"""Internal application and Runtime finalizer lifecycle tests."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob
from flask_xxljob._app import ApplicationRegistry
from flask_xxljob._lifecycle import install_runtime_finalizer, safe_close_runtime
from flask_xxljob.exceptions import XXLJobConfigError, XXLJobError
from flask_xxljob.extension import EXTENSION_KEY
from flask_xxljob.registry.registry_service import RegistryService


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


def test_application_registry_discard_is_idempotent():
    registry = ApplicationRegistry()
    app = Flask("discard")

    registry.add(app)
    assert tuple(registry.snapshot()) == (app,)

    registry.discard(app)
    registry.discard(app)

    assert registry.is_empty
    with pytest.raises(XXLJobError, match="No Flask application"):
        registry.resolve()


@pytest.mark.parametrize(
    "enabled,auto_register,expected_calls",
    [
        (True, True, 1),
        (True, False, 0),
        (False, True, 0),
        (False, False, 0),
    ],
)
def test_init_app_auto_start_uses_creator_owned_prepare_then_activate(
    mocker, enabled, auto_register, expected_calls
):
    token = object()
    prepare = mocker.patch.object(
        RegistryService,
        "_prepare_start",
        autospec=True,
        return_value=token,
    )
    activate = mocker.patch.object(
        RegistryService,
        "_activate_prepared_start",
        autospec=True,
        return_value=True,
    )
    app = configured_app(
        "lifecycle-{}-{}".format(enabled, auto_register),
        XXL_JOB_ENABLED=enabled,
        XXL_JOB_AUTO_REGISTER=auto_register,
    )

    FlaskXXLJob(app)

    assert prepare.call_count == expected_calls
    assert activate.call_count == expected_calls
    if expected_calls:
        service = app.extensions["xxljob"].registry_service
        prepare.assert_called_once_with(service)
        activate.assert_called_once_with(service, token)
    app.extensions["xxljob"].close()


def test_auto_start_prepares_before_flask_commit_and_activates_after(
    mocker,
):
    app = configured_app(
        "prepared-order",
        XXL_JOB_AUTO_REGISTER=True,
    )
    token = object()
    events = []

    def prepare(service):
        assert EXTENSION_KEY not in app.extensions
        assert "xxljob" not in app.cli.commands
        assert not any(
            name.startswith("xxljob_") for name in app.blueprints
        )
        events.append("prepare")
        return token

    def activate(service, prepared):
        assert prepared is token
        assert app.extensions[EXTENSION_KEY].registry_service is service
        assert "xxljob" in app.cli.commands
        assert any(name.startswith("xxljob_") for name in app.blueprints)
        events.append("activate")
        return True

    mocker.patch.object(
        RegistryService, "_prepare_start", autospec=True, side_effect=prepare
    )
    mocker.patch.object(
        RegistryService,
        "_activate_prepared_start",
        autospec=True,
        side_effect=activate,
    )

    FlaskXXLJob(app)

    assert events == ["prepare", "activate"]
    app.extensions["xxljob"].close()


def test_registry_stop_between_commit_and_activation_is_normal(mocker):
    app = configured_app(
        "prepared-cancel",
        XXL_JOB_AUTO_REGISTER=True,
    )
    captured = []
    real_prepare = RegistryService._prepare_start
    real_activate = RegistryService._activate_prepared_start

    def prepare(service):
        prepared = real_prepare(service)
        captured.append(prepared)
        return prepared

    def cancel_then_activate(service, prepared):
        assert EXTENSION_KEY in app.extensions
        service.stop()
        return real_activate(service, prepared)

    mocker.patch.object(
        RegistryService, "_prepare_start", autospec=True, side_effect=prepare
    )
    mocker.patch.object(
        RegistryService,
        "_activate_prepared_start",
        autospec=True,
        side_effect=cancel_then_activate,
    )

    FlaskXXLJob(app)

    prepared = captured[0]
    assert prepared is not None
    prepared.thread.join(timeout=1)
    service = app.extensions[EXTENSION_KEY].registry_service
    state = service._get_process_state()
    assert prepared.thread.is_alive() is False
    assert state.prepared_start is None
    assert state.generation == 0
    assert state.worker is None
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


def test_runtime_finalizer_detach_is_idempotent_and_has_no_lifecycle_effect(
    mocker,
):
    app = Flask("detached-finalizer")
    runtime = mocker.Mock()
    result = install_runtime_finalizer(app, runtime)

    assert result.detach() is not None
    assert result.detach() is None
    assert result() is None

    runtime.close.assert_not_called()
    runtime.registry_service.shutdown.assert_not_called()
    runtime.admin_client.registry.assert_not_called()
    runtime.admin_client.remove.assert_not_called()


def test_safe_close_runtime_swallows_shutdown_errors(mocker):
    runtime = mocker.Mock()
    runtime.close.side_effect = RuntimeError("shutdown")

    safe_close_runtime(runtime)

    runtime.close.assert_called_once_with()

"""Extension initialization and isolation tests."""

from __future__ import annotations

import threading

import click
import pytest
from flask import Blueprint, Flask

from flask_xxljob import FlaskXXLJob, XXLJobResponse
from flask_xxljob._lifecycle import install_runtime_finalizer
from flask_xxljob._logging import XXLJobLogManager
from flask_xxljob.cli.commands import xxljob_cli
from flask_xxljob.client import CallResult
from flask_xxljob.exceptions import (
    XXLJobAlreadyInitializedError,
    XXLJobConfigError,
    XXLJobError,
    XXLJobInitializationError,
)
from flask_xxljob.extension import EXTENSION_KEY
from flask_xxljob.registry.registry_service import RegistryService
from tests.conftest import BASE_CONFIG, make_app


def _capture_log_managers(mocker):
    managers = []
    handlers = []
    close_spies = {}

    def create_manager(*args, **kwargs):
        manager = XXLJobLogManager(*args, **kwargs)
        managers.append(manager)
        for handler in manager.managed_handlers:
            handlers.append(handler)
            close_spies[handler] = mocker.spy(handler, "close")
        return manager

    mocker.patch(
        "flask_xxljob.extension.XXLJobLogManager",
        side_effect=create_manager,
    )
    return managers, handlers, close_spies


def test_lazy_init():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    assert EXTENSION_KEY in app.extensions


def test_direct_init():
    app = Flask("direct")
    app.config.update(BASE_CONFIG)
    ext = FlaskXXLJob(app)
    assert EXTENSION_KEY in app.extensions
    assert ext is not None


def test_runtime_stored_in_extensions(app_ext):
    app, _ = app_ext
    runtime = app.extensions[EXTENSION_KEY]
    assert runtime.config is not None
    assert runtime.callback_registry is not None
    assert runtime.admin_client is not None
    assert runtime.callback_client is not None
    assert runtime.registry_service is not None


def test_double_init_raises():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    with pytest.raises(XXLJobAlreadyInitializedError):
        ext.init_app(app)


def test_invalid_config_raises():
    app = Flask("bad")
    app.config.update(XXL_JOB_ADMIN_ADDRESSES=[])
    with pytest.raises(XXLJobConfigError):
        FlaskXXLJob(app)


def test_multiple_app_runtime_isolation():
    ext = FlaskXXLJob()
    app1, _ = make_app(ext, name="app1")

    @ext.on_run("demoJobHandler")
    def run1(request):
        return XXLJobResponse.success(content="app1")

    app2, _ = make_app(ext, name="app2")

    def run2(request):
        return XXLJobResponse.failure("app2")

    ext.set_run_callback(app2, "demoJobHandler", run2)

    r1 = app1.extensions[EXTENSION_KEY].callback_registry.get_run("demoJobHandler")
    r2 = app2.extensions[EXTENSION_KEY].callback_registry.get_run("demoJobHandler")
    assert r1 is run1
    assert r2 is run2
    assert r1 is not r2


def test_multiple_apps_require_explicit_app_or_context():
    ext = FlaskXXLJob()
    app1, _ = make_app(ext, name="ambiguous1")
    app2, _ = make_app(ext, name="ambiguous2")

    with pytest.raises(XXLJobError, match="Multiple Flask applications"):
        ext.get_status()

    assert ext.get_status(app1).enabled is True
    with app2.app_context():
        assert ext.get_status().enabled is True


def test_blueprint_registered(app_ext):
    app, _ = app_ext
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/run" in rules
    assert "/beat" in rules
    assert "/idleBeat" in rules
    assert "/kill" in rules
    assert "/log" in rules


def test_route_prefix_applied():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="prefixed", XXL_JOB_ROUTE_PREFIX="exec")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/exec/run" in rules


@pytest.mark.parametrize("prefix", ["/xxl-job", "/xxl-job/", "//xxl-job//"])
def test_route_prefix_variants_have_no_double_slash(prefix):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="pfx_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX=prefix)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/xxl-job/run" in rules
    assert not any("//" in rule for rule in rules)


def test_empty_route_prefix_mounts_at_root():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="root_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX="")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/run" in rules


def test_slash_route_prefix_mounts_at_root_and_returns_json_errors():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="slash_root_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX="/")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/run" in rules
    resp = app.test_client().get("/run")
    assert resp.is_json
    assert resp.json["code"] == 500


def test_prefixed_run_dispatches():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="pfxrun_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX="/xxl-job/")

    @ext.on_run("demoJobHandler")
    def handler(request):
        return XXLJobResponse.success(content="prefixed")

    resp = app.test_client().post(
        "/xxl-job/run",
        json={"jobId": 1, "executorHandler": "demoJobHandler"},
    )
    assert resp.json["content"] == "prefixed"


def test_cli_command_registered(app_ext):
    app, _ = app_ext
    assert "xxljob" in app.cli.commands


def test_foreign_cli_command_conflict_fails_during_preflight(mocker):
    app = Flask("cli_conflict")
    app.config.update(BASE_CONFIG)
    foreign = click.Command("xxljob")
    app.cli.add_command(foreign)
    ext = FlaskXXLJob()
    create_log_manager = mocker.patch(
        "flask_xxljob.extension.XXLJobLogManager"
    )
    initial_rules = tuple(app.url_map.iter_rules())
    initial_hooks = {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    }

    with pytest.raises(XXLJobInitializationError, match="CLI command conflict"):
        ext.init_app(app)

    create_log_manager.assert_not_called()
    assert app.cli.commands["xxljob"] is foreign
    assert tuple(app.url_map.iter_rules()) == initial_rules
    assert {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    } == initial_hooks
    assert EXTENSION_KEY not in app.extensions
    assert ext._applications.is_empty  # noqa: SLF001 - preflight contract


def test_project_cli_command_preinstalled_is_an_idempotent_noop():
    app = Flask("cli_preinstalled")
    app.config.update(BASE_CONFIG)
    app.cli.add_command(xxljob_cli)
    ext = FlaskXXLJob()

    ext.init_app(app)

    assert app.cli.commands["xxljob"] is xxljob_cli
    app.extensions[EXTENSION_KEY].close()


@pytest.mark.parametrize("path", ["/beat", "/idleBeat", "/run", "/kill", "/log"])
def test_post_route_conflict_fails_without_partial_initialization(path):
    app = Flask("conflict_" + path.strip("/"))
    app.config.update(BASE_CONFIG)
    app.add_url_rule(path, endpoint="host", view_func=lambda: "host", methods=["POST"])

    with pytest.raises(XXLJobInitializationError, match=path):
        FlaskXXLJob(app)

    assert EXTENSION_KEY not in app.extensions
    assert "xxljob" not in app.cli.commands
    assert not any(name.startswith("xxljob_") for name in app.blueprints)


def test_auto_registry_preflight_failure_is_atomic_and_retryable(
    tmp_path, mocker
):
    app = Flask("preflight_retry")
    log_path = tmp_path / "must-not-exist"
    app.config.update(
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_ADMIN_ADDRESSES=[],
        XXL_JOB_EXECUTOR_ADDRESS="",
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_PATH=str(log_path),
    )
    ext = FlaskXXLJob()
    initial_rules = tuple(
        (rule.rule, rule.endpoint, tuple(sorted(rule.methods or ())))
        for rule in app.url_map.iter_rules()
    )
    initial_blueprints = dict(app.blueprints)
    initial_cli = dict(app.cli.commands)
    initial_hooks = {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    }

    with pytest.raises(XXLJobConfigError):
        ext.init_app(app)

    assert EXTENSION_KEY not in app.extensions
    assert tuple(
        (rule.rule, rule.endpoint, tuple(sorted(rule.methods or ())))
        for rule in app.url_map.iter_rules()
    ) == initial_rules
    assert app.blueprints == initial_blueprints
    assert app.cli.commands == initial_cli
    assert {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    } == initial_hooks
    assert ext._applications.is_empty  # noqa: SLF001 - atomicity contract
    assert not log_path.exists()

    app.config.update(
        XXL_JOB_ADMIN_ADDRESSES=["http://admin:8080"],
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )
    prepare = mocker.patch.object(
        RegistryService, "_prepare_start", autospec=True, return_value=None
    )
    ext.init_app(app)

    assert EXTENSION_KEY in app.extensions
    assert "xxljob" in app.cli.commands
    prepare.assert_called_once_with(
        app.extensions[EXTENSION_KEY].registry_service
    )


def test_finalizer_prepare_does_not_publish_application_state(mocker):
    app = Flask("finalizer_private_prepare")
    app.config.update(
        BASE_CONFIG,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_REGISTRY_INTERVAL=3600,
    )
    ext = FlaskXXLJob()
    registry = mocker.patch(
        "flask_xxljob.client.admin_client.AdminClient.registry",
        return_value=CallResult(success=True, address="http://admin:8080"),
    )
    initial_rules = tuple(app.url_map.iter_rules())
    initial_hooks = {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    }
    observed = []

    def observe_private_prepare(prepared_app, runtime):
        state = runtime.registry_service._get_process_state()
        assert prepared_app is app
        assert EXTENSION_KEY not in app.extensions
        assert ext._applications.is_empty  # noqa: SLF001 - ownership contract
        assert "xxljob" not in app.cli.commands
        assert tuple(app.url_map.iter_rules()) == initial_rules
        assert {
            key: tuple(value)
            for key, value in app.before_request_funcs.items()
        } == initial_hooks
        assert not any(name.startswith("xxljob_") for name in app.blueprints)
        assert state.prepared_start is not None
        assert state.worker is None
        assert state.generation == 0
        assert runtime._finalizer is None  # noqa: SLF001 - private prepare
        assert registry.call_count == 0
        observed.append(runtime)
        return install_runtime_finalizer(prepared_app, runtime)

    mocker.patch(
        "flask_xxljob.extension.install_runtime_finalizer",
        side_effect=observe_private_prepare,
    )

    ext.init_app(app)

    assert observed == [app.extensions[EXTENSION_KEY]]
    runtime = observed[0]
    worker = runtime.registry_service._get_process_state().worker
    runtime.close()
    assert worker is not None and worker.thread is not None
    worker.thread.join(timeout=1)


def test_finalizer_prepare_failure_is_atomic_and_retryable(mocker):
    app = Flask("finalizer_prepare_retry")
    app.config.update(
        BASE_CONFIG,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_REGISTRY_INTERVAL=3600,
    )
    ext = FlaskXXLJob()
    managers, handlers, close_spies = _capture_log_managers(mocker)
    prepared_tokens = []
    real_prepare = RegistryService._prepare_start
    failure = RuntimeError("finalizer prepare failed")
    attempts = 0
    registry_called = threading.Event()

    def capture_prepare(service):
        prepared = real_prepare(service)
        prepared_tokens.append(prepared)
        return prepared

    def fail_once(prepared_app, runtime):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise failure
        return install_runtime_finalizer(prepared_app, runtime)

    def registry_result(*args, **kwargs):
        registry_called.set()
        return CallResult(success=True, address="http://admin:8080")

    mocker.patch.object(
        RegistryService,
        "_prepare_start",
        autospec=True,
        side_effect=capture_prepare,
    )
    mocker.patch(
        "flask_xxljob.extension.install_runtime_finalizer",
        side_effect=fail_once,
    )
    registry = mocker.patch(
        "flask_xxljob.client.admin_client.AdminClient.registry",
        side_effect=registry_result,
    )
    initial_rules = tuple(app.url_map.iter_rules())
    initial_blueprints = dict(app.blueprints)
    initial_cli = dict(app.cli.commands)
    initial_hooks = {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    }

    with pytest.raises(RuntimeError) as raised:
        ext.init_app(app)

    assert raised.value is failure
    assert prepared_tokens[0] is not None
    prepared_tokens[0].thread.join(timeout=1)
    assert prepared_tokens[0].thread.is_alive() is False
    assert registry.call_count == 0
    assert EXTENSION_KEY not in app.extensions
    assert tuple(app.url_map.iter_rules()) == initial_rules
    assert app.blueprints == initial_blueprints
    assert app.cli.commands == initial_cli
    assert {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    } == initial_hooks
    assert ext._applications.is_empty  # noqa: SLF001 - ownership contract
    assert managers[0].managed_handlers == ()
    assert handlers[0] not in managers[0].logger.handlers
    close_spies[handlers[0]].assert_called_once_with()

    ext.init_app(app)

    assert registry_called.wait(timeout=1)
    runtime = app.extensions[EXTENSION_KEY]
    worker = runtime.registry_service._get_process_state().worker
    runtime.close()
    assert worker is not None and worker.thread is not None
    worker.thread.join(timeout=1)


def test_prepared_thread_start_failure_closes_handlers_and_can_retry(
    mocker,
):
    app = Flask("prepared_start_retry")
    app.config.update(
        BASE_CONFIG,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_REGISTRY_INTERVAL=3600,
    )
    ext = FlaskXXLJob()
    managers, handlers, close_spies = _capture_log_managers(mocker)
    install_finalizer = mocker.patch(
        "flask_xxljob.extension.install_runtime_finalizer"
    )
    registry_called = threading.Event()

    def registry_result(*args, **kwargs):
        registry_called.set()
        return CallResult(success=True, address="http://admin:8080")

    registry = mocker.patch(
        "flask_xxljob.client.admin_client.AdminClient.registry",
        side_effect=registry_result,
    )
    real_start = threading.Thread.start
    failed = False

    def fail_first_registry_thread(thread):
        nonlocal failed
        if thread.name == "flask-xxljob-registry" and not failed:
            failed = True
            raise RuntimeError("prepared thread start failed")
        return real_start(thread)

    mocker.patch(
        "flask_xxljob.registry.registry_service.threading.Thread.start",
        new=fail_first_registry_thread,
    )
    initial_rules = tuple(app.url_map.iter_rules())
    initial_blueprints = dict(app.blueprints)
    initial_cli = dict(app.cli.commands)
    initial_hooks = {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    }

    with pytest.raises(
        RuntimeError, match="prepared thread start failed"
    ):
        ext.init_app(app)

    assert EXTENSION_KEY not in app.extensions
    assert tuple(app.url_map.iter_rules()) == initial_rules
    assert app.blueprints == initial_blueprints
    assert app.cli.commands == initial_cli
    assert {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    } == initial_hooks
    assert ext._applications.is_empty  # noqa: SLF001 - atomicity contract
    assert registry.call_count == 0
    install_finalizer.assert_not_called()
    assert len(managers) == 1
    assert managers[0].managed_handlers == ()
    assert handlers[0] not in managers[0].logger.handlers
    close_spies[handlers[0]].assert_called_once_with()

    ext.init_app(app)

    runtime = app.extensions[EXTENSION_KEY]
    state = runtime.registry_service._get_process_state()
    assert state.prepared_start is None
    assert state.worker is not None
    assert len(managers) == 2
    assert len(managers[1].managed_handlers) == 1
    assert handlers[0] not in managers[0].logger.handlers
    assert registry_called.wait(timeout=1)
    assert registry.call_count >= 1
    install_finalizer.assert_called_once_with(app, runtime)
    worker = state.worker
    runtime.close()
    assert worker is not None and worker.thread is not None
    worker.thread.join(timeout=1)


@pytest.mark.parametrize(
    "constructor",
    [
        "CallbackRegistry",
        "AdminClient",
        "CallbackClient",
        "RegistryService",
        "XXLJobRuntime",
    ],
)
def test_uncommitted_constructor_failure_closes_private_handlers(
    mocker, constructor
):
    app = Flask("uncommitted_{}".format(constructor.lower()))
    app.config.update(
        BASE_CONFIG,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
    )
    ext = FlaskXXLJob()
    managers, handlers, close_spies = _capture_log_managers(mocker)
    failure = RuntimeError("{} construction failed".format(constructor))
    mocker.patch(
        "flask_xxljob.extension.{}".format(constructor),
        side_effect=failure,
    )

    with pytest.raises(RuntimeError) as raised:
        ext.init_app(app)

    assert raised.value is failure
    assert EXTENSION_KEY not in app.extensions
    assert ext._applications.is_empty  # noqa: SLF001 - ownership contract
    assert len(managers) == 1
    assert managers[0].managed_handlers == ()
    assert handlers[0] not in managers[0].logger.handlers
    close_spies[handlers[0]].assert_called_once_with()


def test_commit_failure_cancels_prepared_and_closes_private_handlers(
    mocker,
):
    app = Flask("prepared_commit_failure")
    app.config.update(
        BASE_CONFIG,
        XXL_JOB_AUTO_REGISTER=True,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
    )
    ext = FlaskXXLJob()
    managers, handlers, close_spies = _capture_log_managers(mocker)
    prepared_tokens = []
    services = []
    finalizers = []
    real_prepare = RegistryService._prepare_start

    def capture_prepare(service):
        services.append(service)
        prepared = real_prepare(service)
        prepared_tokens.append(prepared)
        return prepared

    def capture_finalizer(prepared_app, runtime):
        finalizer = install_runtime_finalizer(prepared_app, runtime)
        finalizers.append(finalizer)
        return finalizer

    mocker.patch.object(
        RegistryService,
        "_prepare_start",
        autospec=True,
        side_effect=capture_prepare,
    )
    registry = mocker.patch(
        "flask_xxljob.client.admin_client.AdminClient.registry"
    )
    mocker.patch(
        "flask_xxljob.extension.install_runtime_finalizer",
        side_effect=capture_finalizer,
    )
    failure = RuntimeError("controlled Flask commit failure")
    mocker.patch.object(app, "register_blueprint", side_effect=failure)

    with pytest.raises(RuntimeError) as raised:
        ext.init_app(app)

    assert raised.value is failure
    assert len(prepared_tokens) == 1
    prepared = prepared_tokens[0]
    assert prepared is not None
    assert prepared.thread.is_alive() is False
    state = services[0]._get_process_state()
    assert state.prepared_start is None
    assert state.generation == 0
    assert state.worker is None
    assert not state.stopping_workers
    assert registry.call_count == 0
    assert managers[0].managed_handlers == ()
    assert handlers[0] not in managers[0].logger.handlers
    close_spies[handlers[0]].assert_called_once_with()
    assert EXTENSION_KEY not in app.extensions
    assert "xxljob" not in app.cli.commands
    assert ext._applications.is_empty  # noqa: SLF001 - ownership contract
    assert len(finalizers) == 1
    assert finalizers[0].alive is False


def test_commit_failure_preserves_replacement_extension_and_cli(mocker):
    app = Flask("identity_safe_commit_failure")
    app.config.update(
        BASE_CONFIG,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
    )
    ext = FlaskXXLJob()
    managers, handlers, close_spies = _capture_log_managers(mocker)
    finalizers = []
    foreign_runtime = object()
    foreign_cli = click.Command("xxljob")
    failure = RuntimeError("commit ownership replaced")

    def capture_finalizer(prepared_app, runtime):
        finalizer = install_runtime_finalizer(prepared_app, runtime)
        finalizers.append(finalizer)
        return finalizer

    def replace_ownership_then_fail(blueprint):
        app.extensions[EXTENSION_KEY] = foreign_runtime
        app.cli.commands["xxljob"] = foreign_cli
        raise failure

    mocker.patch(
        "flask_xxljob.extension.install_runtime_finalizer",
        side_effect=capture_finalizer,
    )
    mocker.patch.object(
        app,
        "register_blueprint",
        side_effect=replace_ownership_then_fail,
    )

    with pytest.raises(RuntimeError) as raised:
        ext.init_app(app)

    assert raised.value is failure
    assert app.extensions[EXTENSION_KEY] is foreign_runtime
    assert app.cli.commands["xxljob"] is foreign_cli
    assert ext._applications.is_empty  # noqa: SLF001 - identity contract
    assert len(finalizers) == 1
    assert finalizers[0].alive is False
    assert managers[0].managed_handlers == ()
    assert handlers[0] not in managers[0].logger.handlers
    close_spies[handlers[0]].assert_called_once_with()


def test_commit_failure_preserves_preinstalled_project_cli(mocker):
    app = Flask("preinstalled_cli_commit_failure")
    app.config.update(BASE_CONFIG)
    app.cli.add_command(xxljob_cli)
    ext = FlaskXXLJob()
    failure = RuntimeError("commit failed after CLI no-op")
    mocker.patch.object(app, "register_blueprint", side_effect=failure)

    with pytest.raises(RuntimeError) as raised:
        ext.init_app(app)

    assert raised.value is failure
    assert app.cli.commands["xxljob"] is xxljob_cli
    assert EXTENSION_KEY not in app.extensions
    assert ext._applications.is_empty  # noqa: SLF001 - CLI ownership contract


def test_blueprint_name_conflict_fails_during_preflight(tmp_path):
    app = Flask("blueprint_conflict")
    app.config.update(BASE_CONFIG)
    log_path = tmp_path / "must-not-exist"
    app.config.update(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_PATH=str(log_path),
    )
    app.register_blueprint(Blueprint("xxljob_blueprint_conflict", __name__))
    initial_cli = dict(app.cli.commands)
    initial_hooks = {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    }

    with pytest.raises(XXLJobInitializationError, match="blueprint name conflict"):
        FlaskXXLJob(app)

    assert EXTENSION_KEY not in app.extensions
    assert app.cli.commands == initial_cli
    assert {
        key: tuple(value) for key, value in app.before_request_funcs.items()
    } == initial_hooks
    assert not log_path.exists()


def test_prefixed_post_route_conflict_fails():
    app = Flask("prefixed_conflict")
    app.config.update(BASE_CONFIG, XXL_JOB_ROUTE_PREFIX="/executor")
    app.add_url_rule(
        "/executor/run", endpoint="host_run", view_func=lambda: "host", methods=["POST"]
    )

    with pytest.raises(XXLJobInitializationError, match="/executor/run"):
        FlaskXXLJob(app)


def test_get_only_host_route_does_not_conflict():
    app = Flask("get_only")
    app.config.update(BASE_CONFIG)
    app.add_url_rule("/run", endpoint="host_get", view_func=lambda: "host", methods=["GET"])

    FlaskXXLJob(app)

    assert app.test_client().get("/run").data == b"host"


def test_disabled_extension_does_not_check_route_conflicts():
    app = Flask("disabled_conflict")
    app.config.update(BASE_CONFIG, XXL_JOB_ENABLED=False)
    app.add_url_rule("/run", endpoint="host_run", view_func=lambda: "host", methods=["POST"])

    FlaskXXLJob(app)

    assert EXTENSION_KEY in app.extensions
    run_rules = [rule for rule in app.url_map.iter_rules() if rule.rule == "/run"]
    assert len(run_rules) == 1

"""Callback-registration behaviour and executor register/remove API tests."""

from __future__ import annotations

import threading
import time

from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse
from flask_xxljob.client import CallResult
from flask_xxljob.extension import EXTENSION_KEY
from tests.conftest import make_app


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


def test_on_run_returns_named_decorator():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    def handler(request):
        return XXLJobResponse.success()

    ext.on_run("demoJobHandler")(handler)
    assert (
        app.extensions[EXTENSION_KEY]
        .callback_registry.get_run("demoJobHandler")
        is handler
    )


def test_on_all_as_decorators():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    @ext.on_run("demoJobHandler")
    def run(request):
        return XXLJobResponse.success()

    @ext.on_idle_beat
    def idle(request):
        return XXLJobResponse.success()

    @ext.on_kill
    def kill(request):
        return XXLJobResponse.success()

    @ext.on_log
    def log(request):
        return LogResponse()

    registry = app.extensions[EXTENSION_KEY].callback_registry
    assert registry.get_run("demoJobHandler") is run
    assert registry.idle_beat is idle
    assert registry.kill is kill
    assert registry.log is log


def test_register_executor_uses_client(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    called = mocker.patch.object(
        app.extensions[EXTENSION_KEY].registry_service,
        "register_once_result",
    )
    ext.register_executor(app)
    called.assert_called_once()


def test_remove_executor_uses_client(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    called = mocker.patch.object(
        app.extensions[EXTENSION_KEY].registry_service,
        "remove_once_result",
    )
    ext.remove_executor(app)
    called.assert_called_once()


def test_runtime_close_cleans_register_that_entered_before_shutdown(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(
        ext,
        name="register_shutdown_race",
        XXL_JOB_DEREGISTER_ON_EXIT=True,
        XXL_JOB_REGISTRY_INTERVAL=3600,
    )
    runtime = app.extensions[EXTENSION_KEY]
    service = runtime.registry_service
    explicit_started = threading.Event()
    release_explicit = threading.Event()
    operations = []

    def registry(_request):
        operations.append("registry")
        return CallResult(success=True, address="http://admin:8080")

    def registry_remove(_request):
        operations.append("registryRemove")
        return CallResult(success=True, address="http://admin:8080")

    mocker.patch.object(runtime.admin_client, "registry", side_effect=registry)
    mocker.patch.object(
        runtime.admin_client,
        "registry_remove",
        side_effect=registry_remove,
    )

    ext.start_registry(app)
    _wait_for(lambda: operations == ["registry"])
    _wait_for(lambda: service.status_snapshot()["registered"] is True)

    original_call_registry = service._call_registry

    def gated_one_shot(current_state, *, remove):
        if not remove:
            explicit_started.set()
            release_explicit.wait(timeout=5)
        return original_call_registry(current_state, remove=remove)

    mocker.patch.object(
        service,
        "_call_registry",
        side_effect=gated_one_shot,
    )

    results = []
    register = threading.Thread(
        target=lambda: results.append(ext.register_executor(app))
    )
    register.start()
    assert explicit_started.wait(timeout=1)

    state = service._get_process_state()
    _wait_for(
        lambda: state.register_coordination is not None
        and state.register_coordination.inflight_count == 1
    )
    close_done = threading.Event()
    close = threading.Thread(
        target=lambda: (runtime.close(), close_done.set())
    )
    close.start()

    assert close_done.wait(timeout=1)
    close.join(timeout=1)
    coordination = state.register_coordination
    assert coordination is not None
    assert coordination.cleanup_requested is True
    assert state.pending_remove is None
    assert state.active_remove is None
    assert operations == ["registry"]

    release_explicit.set()
    register.join(timeout=2)
    assert not register.is_alive()
    _wait_for(lambda: operations == ["registry", "registry", "registryRemove"])
    _wait_for(
        lambda: state.register_coordination is None
        and state.pending_remove is None
        and state.active_remove is None
        and not state.cleanup_actors
        and not state.stopping_workers
    )

    assert len(results) == 1
    assert results[0].success is True
    assert service.is_running is False
    assert service.status_snapshot()["registered"] is False


def test_callback_within_app_context(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    post = mocker.patch("flask_xxljob.client.requests.post")
    post.return_value = mocker.Mock(status_code=200, json=lambda: {"code": 200, "msg": None})
    with app.app_context():
        result = ext.callback_success(log_id=1, log_date_time=2, message="done")
    assert result.success is True


def test_callback_failure_uses_fail_code(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    post = mocker.patch("flask_xxljob.client.requests.post")
    post.return_value = mocker.Mock(status_code=200, json=lambda: {"code": 200, "msg": None})
    with app.app_context():
        ext.callback_failure(log_id=1, log_date_time=2, message="oops")
    assert post.call_args.kwargs["json"][0]["handleCode"] == 500

"""Application-level callback registration tests (0.2.0)."""

from __future__ import annotations

import pytest

from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse
from flask_xxljob.exceptions import XXLJobCallbackRegistrationError
from tests.conftest import make_app


def _run(request):
    return XXLJobResponse.success(content="run")


def _idle(request):
    return XXLJobResponse.success()


def _kill(request):
    return XXLJobResponse.success()


def _log(request):
    return LogResponse()


def test_register_callbacks_default_app():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    with app.app_context():
        ext.register_callbacks(run=_run, idle_beat=_idle, kill=_kill, log=_log)
    assert ext.get_run_callback(app) is _run
    assert ext.get_idle_beat_callback(app) is _idle
    assert ext.get_kill_callback(app) is _kill
    assert ext.get_log_callback(app) is _log


def test_register_callbacks_explicit_app():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    ext.register_callbacks(app, run=_run)
    assert ext.get_run_callback(app) is _run


def test_set_callbacks_explicit_app():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    ext.set_run_callback(app, _run)
    ext.set_idle_beat_callback(app, _idle)
    ext.set_kill_callback(app, _kill)
    ext.set_log_callback(app, _log)
    assert ext.get_run_callback(app) is _run
    assert ext.get_idle_beat_callback(app) is _idle
    assert ext.get_kill_callback(app) is _kill
    assert ext.get_log_callback(app) is _log


def test_multi_app_isolation():
    ext = FlaskXXLJob()
    app1, _ = make_app(ext, name="app1")
    app2, _ = make_app(ext, name="app2")

    def r1(request):
        return XXLJobResponse.success(content="one")

    def r2(request):
        return XXLJobResponse.success(content="two")

    ext.set_run_callback(app1, r1)
    ext.set_run_callback(app2, r2)
    assert ext.get_run_callback(app1) is r1
    assert ext.get_run_callback(app2) is r2
    assert app1.test_client().post("/run", json={"jobId": 1}).json["content"] == "one"
    assert app2.test_client().post("/run", json={"jobId": 1}).json["content"] == "two"


def test_duplicate_registration_raises():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    ext.set_run_callback(app, _run)
    with pytest.raises(XXLJobCallbackRegistrationError):
        ext.set_run_callback(app, _run)


def test_replace_true_overrides():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    def r2(request):
        return XXLJobResponse.success(content="two")

    ext.set_run_callback(app, _run)
    ext.set_run_callback(app, r2, replace=True)
    assert ext.get_run_callback(app) is r2


def test_module_level_decorator_seeds_factory_apps():
    ext = FlaskXXLJob()

    @ext.on_run
    def run(request):
        return XXLJobResponse.success(content="seeded")

    app, _ = make_app(ext)
    assert ext.get_run_callback(app) is run
    assert app.test_client().post("/run", json={"jobId": 1}).json["content"] == "seeded"


def test_dispatch_uses_app_specific_priority():
    ext = FlaskXXLJob()

    @ext.on_run
    def default_run(request):
        return XXLJobResponse.success(content="default")

    app, _ = make_app(ext)

    def app_run(request):
        return XXLJobResponse.success(content="app")

    ext.set_run_callback(app, app_run, replace=True)
    assert app.test_client().post("/run", json={"jobId": 1}).json["content"] == "app"


def test_handler_exception_returns_failure():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    def boom(request):
        raise RuntimeError("kaboom")

    ext.set_run_callback(app, boom)
    body = app.test_client().post("/run", json={"jobId": 1}).json
    assert body["code"] == 500
    assert "kaboom" not in (body.get("msg") or "")


def test_handler_bad_return_type_returns_failure():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    ext.set_run_callback(app, lambda request: {"not": "a response"})
    body = app.test_client().post("/run", json={"jobId": 1}).json
    assert body["code"] == 500

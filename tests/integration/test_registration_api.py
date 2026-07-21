"""Callback-registration behaviour and executor register/remove API tests."""

from __future__ import annotations

from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse
from flask_xxljob.extension import EXTENSION_KEY
from tests.conftest import make_app


def test_on_run_as_method():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    def handler(request):
        return XXLJobResponse.success()

    ext.on_run(handler)
    assert app.extensions[EXTENSION_KEY].callback_registry.run is handler


def test_on_all_as_decorators():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    @ext.on_run
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
    assert registry.run is run
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

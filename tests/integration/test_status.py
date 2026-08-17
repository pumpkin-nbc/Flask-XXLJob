"""Plugin status and lifecycle tests (0.2.0)."""

from __future__ import annotations

from dataclasses import fields

import pytest

from flask_xxljob import FlaskXXLJob, XXLJobStatus
from flask_xxljob.exceptions import XXLJobError
from tests.conftest import make_app


class FakeResponse:
    def __init__(self, code=200, status_code=200):
        self.status_code = status_code
        self._code = code

    def json(self):
        return {"code": self._code, "msg": "m"}


def test_initial_status():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    status = ext.get_status(app)
    assert isinstance(status, XXLJobStatus)
    assert status.enabled is True
    assert status.auto_register is False
    assert status.registered is False
    assert status.last_registry_time is None
    assert status.registry_thread_running is False
    assert status.log_enabled is False
    assert status.log_level == "INFO"
    assert status.log_file_enabled is False
    assert status.log_console_enabled is False
    assert status.log_file is None


def test_public_status_fields_remain_unchanged():
    assert [item.name for item in fields(XXLJobStatus)] == [
        "enabled",
        "auto_register",
        "registered",
        "last_registry_time",
        "last_registry_success",
        "last_registry_admin_address",
        "last_registry_error_type",
        "last_registry_message",
        "registry_thread_running",
        "log_enabled",
        "log_level",
        "log_file_enabled",
        "log_console_enabled",
        "log_file",
    ]


def test_logging_status_reports_effective_outputs(tmp_path):
    ext = FlaskXXLJob()
    app, _ = make_app(
        ext,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_LEVEL="DEBUG",
        XXL_JOB_LOG_PATH=str(tmp_path),
    )

    status = ext.get_status(app)

    assert status.log_enabled is True
    assert status.log_level == "DEBUG"
    assert status.log_file_enabled is True
    assert status.log_console_enabled is True
    assert status.log_file == str((tmp_path / "flask-xxljob.log").resolve())


def test_status_after_success(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    ext.register_executor(app)
    status = ext.get_status(app)
    assert status.registered is True
    assert status.last_registry_success is True
    assert status.last_registry_admin_address == "http://admin-1:8080/xxl-job-admin"


def test_status_after_failure(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    mocker.patch(
        "flask_xxljob.client.requests.post", return_value=FakeResponse(code=500)
    )
    ext.register_executor(app)
    status = ext.get_status(app)
    assert status.registered is False
    assert status.last_registry_success is False
    assert status.last_registry_error_type == "business"


def test_status_multi_app_isolation(mocker):
    ext = FlaskXXLJob()
    app1, _ = make_app(ext, name="s1")
    app2, _ = make_app(ext, name="s2")
    mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    ext.register_executor(app1)
    assert ext.get_status(app1).registered is True
    assert ext.get_status(app2).registered is False


def test_status_no_sensitive_fields():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, XXL_JOB_ACCESS_TOKEN="secret-token")
    status = ext.get_status(app)
    for value in vars(status).values():
        assert value != "secret-token"


def test_get_status_without_context_raises():
    ext = FlaskXXLJob()
    with pytest.raises(XXLJobError):
        ext.get_status()


def test_cli_status(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["xxljob", "status"])
    assert result.exit_code == 0
    assert "Flask-XXLJob status" in result.output
    assert "Log enabled: False" in result.output
    assert "File logging: False" in result.output
    assert "Console logging: False" in result.output


def test_cli_status_nonzero_on_failure(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    mocker.patch(
        "flask_xxljob.client.requests.post", return_value=FakeResponse(code=500)
    )
    ext.register_executor(app)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["xxljob", "status"])
    assert result.exit_code == 1


def test_cli_status_no_token(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, XXL_JOB_ACCESS_TOKEN="secret-token")
    runner = app.test_cli_runner()
    result = runner.invoke(args=["xxljob", "status"])
    assert "secret-token" not in result.output


def test_start_stop_registry(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    start = mocker.patch.object(
        app.extensions["xxljob"].registry_service, "start"
    )
    stop = mocker.patch.object(app.extensions["xxljob"].registry_service, "stop")
    ext.start_registry(app)
    ext.stop_registry(app)
    start.assert_called_once()
    stop.assert_called_once_with(remove=False)


def test_stop_registry_can_keep_shared_executor_registration(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    stop = mocker.patch.object(app.extensions["xxljob"].registry_service, "stop")

    ext.stop_registry(app, remove=False)

    stop.assert_called_once_with(remove=False)

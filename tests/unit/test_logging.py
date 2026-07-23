"""Managed file and console logging tests."""

from __future__ import annotations

import io
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
import requests
from flask import Flask

from flask_xxljob import FlaskXXLJob
from flask_xxljob.exceptions import XXLJobConfigError, XXLJobInitializationError
from tests.conftest import BASE_CONFIG, make_app


def _runtime(app):
    return app.extensions["xxljob"]


def _log(app, message="logging-test-marker", level=logging.INFO):
    runtime = _runtime(app)
    runtime.log_manager.get_logger("test").log(level, message)
    for handler in runtime.log_manager.managed_handlers:
        handler.flush()


def _managed_handlers(app):
    return _runtime(app).log_manager.managed_handlers


def test_logging_defaults_are_disabled_without_side_effects(tmp_path, capsys):
    root = logging.getLogger()
    root_level = root.level
    root_handlers = tuple(root.handlers)
    app = Flask("default-logging")
    app_logger_level = app.logger.level
    app_logger_handlers = tuple(app.logger.handlers)
    log_dir = tmp_path / "must-not-exist"
    app.config.update(BASE_CONFIG)
    app.config["XXL_JOB_LOG_PATH"] = str(log_dir)

    FlaskXXLJob(app)
    _log(app)

    assert _managed_handlers(app) == ()
    assert not log_dir.exists()
    assert capsys.readouterr() == ("", "")
    assert root.level == root_level
    assert tuple(root.handlers) == root_handlers
    assert app.logger.level == app_logger_level
    assert tuple(app.logger.handlers) == app_logger_handlers


def test_disabled_extension_never_creates_managed_logging(tmp_path):
    app, _ = make_app(
        XXL_JOB_ENABLED=False,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_PATH=str(tmp_path / "must-not-exist"),
    )

    assert _managed_handlers(app) == ()
    assert _runtime(app).log_manager.effective_enabled is False
    assert not (tmp_path / "must-not-exist").exists()


def test_file_logging_uses_absolute_path_and_no_console(tmp_path, capsys):
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=False,
        XXL_JOB_LOG_PATH=str(tmp_path / "logs"),
        XXL_JOB_LOG_FORMAT="%(levelname)s|%(name)s|%(message)s",
    )

    _log(app)

    runtime = _runtime(app)
    handlers = _managed_handlers(app)
    assert len(handlers) == 1
    assert isinstance(handlers[0], RotatingFileHandler)
    assert Path(runtime.log_manager.log_file).is_absolute()
    content = Path(runtime.log_manager.log_file).read_text(encoding="utf-8")
    assert content.count("logging-test-marker") == 1
    assert "INFO|flask_xxljob.app." in content
    assert capsys.readouterr() == ("", "")


def test_console_only_prints_normal_and_error_records(tmp_path, capsys):
    log_dir = tmp_path / "must-not-exist"
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_PATH=str(log_dir),
        XXL_JOB_LOG_LEVEL="DEBUG",
        XXL_JOB_LOG_FORMAT="%(levelname)s|%(message)s",
    )

    _log(app, "normal-record", logging.INFO)
    _log(app, "error-record", logging.ERROR)

    captured = capsys.readouterr()
    assert captured.err.count("INFO|normal-record") == 1
    assert captured.err.count("ERROR|error-record") == 1
    assert captured.out == ""
    assert not log_dir.exists()
    assert len(_managed_handlers(app)) == 1
    assert not isinstance(_managed_handlers(app)[0], RotatingFileHandler)


def test_file_and_console_each_receive_one_record(tmp_path, capsys):
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_PATH=str(tmp_path),
        XXL_JOB_LOG_FORMAT="COMMON|%(levelname)s|%(message)s",
    )

    _log(app)

    output = capsys.readouterr().err
    content = Path(_runtime(app).log_manager.log_file).read_text(encoding="utf-8")
    assert output.count("COMMON|INFO|logging-test-marker") == 1
    assert content.count("COMMON|INFO|logging-test-marker") == 1
    assert len(_managed_handlers(app)) == 2


def test_console_colors_every_standard_level_but_file_stays_plain(tmp_path, capsys):
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_PATH=str(tmp_path),
        XXL_JOB_LOG_LEVEL="DEBUG",
        XXL_JOB_LOG_FORMAT="%(levelname)s|%(message)s",
    )
    colors = {
        logging.DEBUG: "\033[34m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }

    for level in colors:
        _log(app, f"color-{logging.getLevelName(level)}", level)

    console = capsys.readouterr().err
    file_content = Path(_runtime(app).log_manager.log_file).read_text(
        encoding="utf-8"
    )
    for level, color in colors.items():
        name = logging.getLevelName(level)
        assert f"{color}{name}|color-{name}\033[0m" in console
        assert f"{name}|color-{name}" in file_content
    assert "\033[" not in file_content


def test_no_managed_targets_preserves_host_logger_configuration(tmp_path):
    package_logger = logging.getLogger("flask_xxljob")
    previous_level = package_logger.level
    previous_propagate = package_logger.propagate
    stream = io.StringIO()
    host_handler = logging.StreamHandler(stream)
    package_logger.addHandler(host_handler)
    package_logger.setLevel(logging.INFO)
    try:
        app, _ = make_app(
            XXL_JOB_LOG_ENABLED=True,
            XXL_JOB_LOG_FILE_ENABLED=False,
            XXL_JOB_LOG_CONSOLE_ENABLED=False,
            XXL_JOB_LOG_PATH=str(tmp_path / "must-not-exist"),
        )
        manager = _runtime(app).log_manager
        manager_level = manager.logger.level
        manager_propagate = manager.logger.propagate

        _log(app, "host-managed-marker")

        assert manager.managed_handlers == ()
        assert manager.logger.level == manager_level == logging.NOTSET
        assert manager.logger.propagate is manager_propagate is True
        assert stream.getvalue().count("host-managed-marker") == 1
        assert not (tmp_path / "must-not-exist").exists()
    finally:
        package_logger.removeHandler(host_handler)
        package_logger.setLevel(previous_level)
        package_logger.propagate = previous_propagate
        host_handler.close()


def test_log_level_applies_to_all_managed_targets(tmp_path, capsys):
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_PATH=str(tmp_path),
        XXL_JOB_LOG_LEVEL="warning",
        XXL_JOB_LOG_FORMAT="%(levelname)s|%(message)s",
    )

    _log(app, "hidden-debug", logging.DEBUG)
    _log(app, "visible-warning", logging.WARNING)

    output = capsys.readouterr().err
    content = Path(_runtime(app).log_manager.log_file).read_text(encoding="utf-8")
    assert "hidden-debug" not in output + content
    assert output.count("WARNING|visible-warning") == 1
    assert content.count("WARNING|visible-warning") == 1
    assert all(handler.level == logging.WARNING for handler in _managed_handlers(app))


def test_rotating_file_handler_rotates(tmp_path):
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=False,
        XXL_JOB_LOG_PATH=str(tmp_path),
        XXL_JOB_LOG_MAX_BYTES=120,
        XXL_JOB_LOG_BACKUP_COUNT=2,
        XXL_JOB_LOG_FORMAT="%(message)s",
    )

    for index in range(20):
        _log(app, f"rotation-{index}-" + ("x" * 30))

    path = Path(_runtime(app).log_manager.log_file)
    assert path.exists()
    assert Path(str(path) + ".1").exists()


def test_runtime_close_removes_only_managed_handlers_and_is_idempotent(tmp_path):
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_PATH=str(tmp_path),
    )
    runtime = _runtime(app)
    managed = runtime.log_manager.managed_handlers
    stream = io.StringIO()
    user_handler = logging.StreamHandler(stream)
    runtime.log_manager.logger.addHandler(user_handler)

    runtime.close()
    runtime.close()

    assert runtime.log_manager.managed_handlers == ()
    assert user_handler in runtime.log_manager.logger.handlers
    assert sys.stdout.closed is False
    assert sys.stderr.closed is False
    runtime.log_manager.logger.removeHandler(user_handler)
    user_handler.close()
    assert managed
    assert all(handler not in runtime.log_manager.logger.handlers for handler in managed)


def test_runtime_close_tolerates_an_already_closed_console_stream():
    app, _ = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
    )
    runtime = _runtime(app)
    handler = runtime.log_manager.managed_handlers[0]
    closed_stream = io.StringIO()
    closed_stream.close()
    handler.stream = closed_stream  # type: ignore[attr-defined]

    runtime.close()

    assert runtime.log_manager.managed_handlers == ()


def test_same_named_apps_have_isolated_unique_loggers(tmp_path, capsys):
    app_a, _ = make_app(
        name="same/name",
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=False,
        XXL_JOB_LOG_PATH=str(tmp_path / "a"),
    )
    app_b, _ = make_app(
        name="same/name",
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_LEVEL="ERROR",
    )
    manager_a = _runtime(app_a).log_manager
    manager_b = _runtime(app_b).log_manager

    assert manager_a.name != manager_b.name
    assert "same_name" in manager_a.name
    assert "0x" not in manager_a.name + manager_b.name

    _log(app_a, "only-file")
    _log(app_b, "hidden-console", logging.INFO)
    _log(app_b, "only-console", logging.ERROR)
    manager_a.close()
    _log(app_b, "still-console", logging.ERROR)

    output = capsys.readouterr().err
    file_content = Path(manager_a.log_file).read_text(encoding="utf-8")
    assert "only-file" in file_content
    assert "only-file" not in output
    assert "hidden-console" not in output
    assert output.count("only-console") == 1
    assert output.count("still-console") == 1
    assert manager_b.managed_handlers


@pytest.mark.parametrize("console_enabled", [False, True])
def test_managed_outputs_redact_sensitive_values(
    tmp_path, capsys, console_enabled
):
    token = "token-super-secret"
    app, ext = make_app(
        XXL_JOB_ACCESS_TOKEN=token,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_CONSOLE_ENABLED=console_enabled,
        XXL_JOB_LOG_PATH=str(tmp_path),
        XXL_JOB_LOG_LEVEL="DEBUG",
        XXL_JOB_LOG_FORMAT="%(message)s",
    )
    sensitive = (
        f"{token} Authorization=Bearer Secret, Cookie=session-secret; "
        "password=hunter2 executorParams=business-secret "
        "glueSource=source-secret handleMsg=message-secret "
        "-----BEGIN PRIVATE KEY-----private-secret-----END PRIVATE KEY-----"
    )

    _log(app, sensitive, logging.DEBUG)
    runtime = _runtime(app)
    runtime.registry_service._record(  # noqa: SLF001 - verify status redaction
        type("Result", (), {
            "success": False,
            "address": None,
            "error_type": "business",
            "message": sensitive,
        })(),
        is_remove=False,
    )

    outputs = Path(runtime.log_manager.log_file).read_text(encoding="utf-8")
    if console_enabled:
        outputs += capsys.readouterr().err
    for secret in (
        token,
        "Bearer Secret",
        "session-secret",
        "hunter2",
        "business-secret",
        "source-secret",
        "message-secret",
        "private-secret",
    ):
        assert secret not in outputs
        assert secret not in (ext.get_status(app).last_registry_message or "")
    assert "<redacted>" in outputs


def test_protocol_logs_safe_failure_categories(tmp_path, capsys):
    token = "protocol-token-secret"
    app, ext = make_app(
        XXL_JOB_ACCESS_TOKEN=token,
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_FORMAT="%(message)s",
    )

    @ext.on_run("known")
    def _run(_request):
        raise RuntimeError("user-secret-message")

    client = app.test_client()
    client.post("/beat", headers={"XXL-JOB-ACCESS-TOKEN": "wrong-secret"})
    client.post(
        "/run",
        data=b"{not-json-business-secret",
        headers={
            "Content-Type": "application/json",
            "XXL-JOB-ACCESS-TOKEN": token,
        },
    )
    client.post(
        "/run",
        json={"executorHandler": "unknown", "executorParams": "business-secret"},
        headers={"XXL-JOB-ACCESS-TOKEN": token},
    )
    client.post(
        "/run",
        json={"executorHandler": "known", "executorParams": "business-secret"},
        headers={"XXL-JOB-ACCESS-TOKEN": token},
    )

    output = capsys.readouterr().err
    assert "access token validation failed" in output
    assert "request parsing failed" in output
    assert "unsupported_handler=unknown" in output
    assert "exception_type=RuntimeError" in output
    for secret in (
        token,
        "wrong-secret",
        "not-json-business-secret",
        "business-secret",
        "user-secret-message",
    ):
        assert secret not in output


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("XXL_JOB_LOG_ENABLED", 1),
        ("XXL_JOB_LOG_FILE_ENABLED", "yes"),
        ("XXL_JOB_LOG_CONSOLE_ENABLED", 1),
        ("XXL_JOB_LOG_PROPAGATE", 0),
        ("XXL_JOB_LOG_LEVEL", "TRACE"),
        ("XXL_JOB_LOG_ENCODING", "not-an-encoding"),
        ("XXL_JOB_LOG_MAX_BYTES", 0),
        ("XXL_JOB_LOG_BACKUP_COUNT", -1),
        ("XXL_JOB_LOG_PATH", ""),
        ("XXL_JOB_LOG_FILENAME", None),
        ("XXL_JOB_LOG_DATE_FORMAT", None),
        ("XXL_JOB_LOG_DATE_FORMAT", 123),
        ("XXL_JOB_LOG_FORMAT", "%(missing_field)s"),
    ],
)
def test_invalid_logging_configuration_rolls_back(key, value, tmp_path):
    app = Flask(f"invalid-{key}")
    app.config.update(BASE_CONFIG)
    app.config.update(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_PATH=str(tmp_path / "must-not-exist"),
    )
    app.config[key] = value

    with pytest.raises(XXLJobConfigError):
        FlaskXXLJob(app)

    assert "xxljob" not in app.extensions
    assert not (tmp_path / "must-not-exist").exists()


def test_logging_initialization_failure_has_no_runtime_state(tmp_path):
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("occupied", encoding="utf-8")
    app = Flask("logging-init-failure")
    app.config.update(BASE_CONFIG)
    app.config.update(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_PATH=str(not_a_directory),
    )

    with pytest.raises(XXLJobInitializationError):
        FlaskXXLJob(app)

    assert "xxljob" not in app.extensions


def test_callback_event_does_not_log_handle_message(tmp_path, capsys, mocker):
    app, ext = make_app(
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_FORMAT="%(message)s",
    )
    response = mocker.Mock(status_code=200)
    response.json.return_value = {"code": 200, "msg": "ok"}
    mocker.patch("flask_xxljob.client.requests.post", return_value=response)

    result = ext.callback_success(1, 2, "handle-message-secret", app=app)

    assert result.success is True
    output = capsys.readouterr().err
    assert "callback succeeded" in output
    assert "handle-message-secret" not in output


def test_admin_failover_registry_renewal_removal_and_callback_events(
    capsys, mocker
):
    class Response:
        def __init__(self, code):
            self.status_code = 200
            self._code = code

        def json(self):
            return {"code": self._code, "msg": "admin-message-secret"}

    app, ext = make_app(
        XXL_JOB_ADMIN_ADDRESSES=["http://admin-a:8080", "http://admin-b:8080"],
        XXL_JOB_LOG_ENABLED=True,
        XXL_JOB_LOG_FILE_ENABLED=False,
        XXL_JOB_LOG_CONSOLE_ENABLED=True,
        XXL_JOB_LOG_FORMAT="%(message)s",
    )
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[
            requests.ConnectionError("network-message-secret"),
            Response(200),
            Response(200),
            Response(500),
            Response(200),
        ],
    )
    runtime = _runtime(app)

    assert ext.register_executor(app).success is True
    assert runtime.registry_service.register_once_result(
        operation="renewal"
    ).success is True
    assert ext.callback_success(1, 2, "handle-message-secret", app=app).success is False
    assert ext.remove_executor(app).success is True

    output = capsys.readouterr().err
    assert "Failing over to the next Admin address" in output
    assert "executor registration succeeded" in output
    assert "executor renewal succeeded" in output
    assert "callback failed" in output
    assert "executor removal succeeded" in output
    assert post.call_count == 5
    for secret in (
        "network-message-secret",
        "admin-message-secret",
        "handle-message-secret",
    ):
        assert secret not in output

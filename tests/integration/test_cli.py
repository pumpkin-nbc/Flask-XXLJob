"""CLI command tests."""

from __future__ import annotations

import threading
import time

import pytest
from click.testing import CliRunner
from flask.cli import ScriptInfo

from flask_xxljob import FlaskXXLJob
from flask_xxljob.cli.commands import standalone_cli, xxljob_cli
from flask_xxljob.client import CallResult
from flask_xxljob.extension import EXTENSION_KEY
from tests.conftest import make_app


def test_cli_register_success(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="cli_app")
    mocker.patch.object(
        app.extensions[EXTENSION_KEY].registry_service,
        "register_once_result",
        return_value=CallResult(success=True, address="http://a:8080"),
    )
    runner = CliRunner()
    result = runner.invoke(xxljob_cli, ["register"], obj=_script_info(app))
    assert result.exit_code == 0
    assert "registered successfully" in result.output


def test_cli_remove_failure(mocker):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="cli_app2")
    service = app.extensions[EXTENSION_KEY].registry_service
    stop = mocker.patch.object(service, "stop")
    mocker.patch.object(
        service,
        "remove_once_result",
        return_value=CallResult(success=False, error="down"),
    )
    runner = CliRunner()
    result = runner.invoke(xxljob_cli, ["remove"], obj=_script_info(app))
    assert result.exit_code != 0
    stop.assert_called_once_with()


@pytest.mark.parametrize("command_kind", ["flask", "standalone"])
@pytest.mark.parametrize("remove_success", [True, False])
def test_cli_remove_stops_registry_even_when_remote_remove_fails(
    mocker, command_kind, remove_success
):
    ext = FlaskXXLJob()
    app, _ = make_app(
        ext,
        name=f"cli_lifecycle_{command_kind}_{remove_success}",
        XXL_JOB_DEREGISTER_ON_EXIT=True,
    )
    runtime = app.extensions[EXTENSION_KEY]
    service = runtime.registry_service
    registry_called = threading.Event()
    registry_calls = []

    def registry(_request):
        registry_calls.append(time.monotonic())
        registry_called.set()
        return CallResult(success=True, address="http://admin:8080")

    mocker.patch.object(runtime.admin_client, "registry", side_effect=registry)
    remove = mocker.patch.object(
        runtime.admin_client,
        "registry_remove",
        return_value=CallResult(
            success=remove_success,
            address="http://admin:8080",
            error=None if remove_success else "down",
            error_type=None if remove_success else "network",
        ),
    )

    ext.start_registry(app)
    assert registry_called.wait(1.0)
    runtime.config.registry_interval = 0.05
    mocker.patch.object(runtime.config, "validate_registry")

    runner = CliRunner()
    if command_kind == "flask":
        result = runner.invoke(xxljob_cli, ["remove"], obj=_script_info(app))
    else:
        mocker.patch.object(ScriptInfo, "load_app", return_value=app)
        result = runner.invoke(standalone_cli, ["remove"])

    assert result.exit_code == (0 if remove_success else 1)
    assert service.is_running is False
    calls_after_remove = len(registry_calls)
    time.sleep(runtime.config.registry_interval * 2.5)
    assert len(registry_calls) == calls_after_remove

    state = service._get_process_state()  # noqa: SLF001 - thread cleanup assertion
    with state.state_lock:
        stopping = tuple(state.stopping_workers.values())
    for context in stopping:
        if context.thread is not None:
            context.thread.join(timeout=1.0)

    runtime.close()
    expected_remove_calls = 1 if remove_success else 2
    wait_deadline = time.monotonic() + 1.0
    while (
        remove.call_count < expected_remove_calls
        and time.monotonic() < wait_deadline
    ):
        time.sleep(0.005)
    assert remove.call_count == expected_remove_calls


def _script_info(app):
    info = ScriptInfo()
    info.load_app = lambda: app  # type: ignore[assignment]
    return info

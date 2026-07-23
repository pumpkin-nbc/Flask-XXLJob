"""CLI command tests."""

from __future__ import annotations

from click.testing import CliRunner

from flask_xxljob import FlaskXXLJob
from flask_xxljob.cli.commands import xxljob_cli
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
    mocker.patch.object(
        app.extensions[EXTENSION_KEY].registry_service,
        "remove_once_result",
        return_value=CallResult(success=False, error="down"),
    )
    runner = CliRunner()
    result = runner.invoke(xxljob_cli, ["remove"], obj=_script_info(app))
    assert result.exit_code != 0


def _script_info(app):
    from flask.cli import ScriptInfo

    info = ScriptInfo()
    info.load_app = lambda: app  # type: ignore[assignment]
    return info

"""
Flask-XXLJob CLI 命令。

Flask-XXLJob CLI commands.

提供 Flask CLI 分组 ``xxljob``（``register`` / ``remove``），以及独立的
``flask-xxljob`` 控制台脚本。CLI 只负责加载 Flask 应用并调用执行器注册/注销，
不启动或执行任何业务任务。

Provides the Flask CLI group ``xxljob`` (``register`` / ``remove``) and a
standalone ``flask-xxljob`` console script. The CLI only loads the Flask
application and triggers executor registration/deregistration; it never starts
or runs any business task.
"""

from __future__ import annotations

import sys
from typing import Any, List, Optional

import click
from flask import current_app
from flask.cli import ScriptInfo, with_appcontext

from .. import __version__
from ..extension import EXTENSION_KEY


def _runtime() -> Any:
    runtime = current_app.extensions.get(EXTENSION_KEY)
    if runtime is None:
        raise click.ClickException(
            "Flask-XXLJob is not initialized on this application."
        )
    return runtime


@click.group(name="xxljob")
def xxljob_cli() -> None:
    """XXL-JOB 执行器管理命令。 / XXL-JOB executor management commands."""


@xxljob_cli.command(name="register")
@with_appcontext
def register_command() -> None:
    """注册执行器到 XXL-JOB Admin。 / Register the executor with the admin."""
    result = _runtime().registry_service.register_once_result()
    if result.success:
        click.echo(f"Executor registered successfully via {result.address}.")
    else:
        click.echo(
            f"Executor registration failed: {result.error or result.msg}", err=True
        )
        raise SystemExit(1)


@xxljob_cli.command(name="remove")
@with_appcontext
def remove_command() -> None:
    """从 XXL-JOB Admin 注销执行器。 / Deregister the executor from the admin."""
    result = _runtime().registry_service.remove_once_result()
    if result.success:
        click.echo(f"Executor removed successfully via {result.address}.")
    else:
        click.echo(
            f"Executor removal failed: {result.error or result.msg}", err=True
        )
        raise SystemExit(1)


@click.group(name="flask-xxljob")
@click.version_option(version=__version__, prog_name="flask-xxljob")
@click.option("--app", "app_import_path", default=None, help="Flask application import path.")
@click.pass_context
def standalone_cli(ctx: click.Context, app_import_path: Optional[str]) -> None:
    """
    独立的 Flask-XXLJob 命令行工具。

    Standalone Flask-XXLJob command-line tool.
    """
    ctx.obj = ScriptInfo(app_import_path=app_import_path)


def _run_standalone(ctx: click.Context, action: str) -> None:
    script_info: ScriptInfo = ctx.obj
    try:
        app = script_info.load_app()
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(f"Failed to load Flask application: {exc}") from exc

    runtime = app.extensions.get(EXTENSION_KEY)
    if runtime is None:
        raise click.ClickException(
            "Flask-XXLJob is not initialized on this application."
        )

    with app.app_context():
        if action == "register":
            result = runtime.registry_service.register_once_result()
            verb = "registered"
        else:
            result = runtime.registry_service.remove_once_result()
            verb = "removed"

    if result.success:
        click.echo(f"Executor {verb} successfully via {result.address}.")
    else:
        click.echo(f"Executor {action} failed: {result.error or result.msg}", err=True)
        raise SystemExit(1)


@standalone_cli.command(name="register")
@click.pass_context
def standalone_register(ctx: click.Context) -> None:
    """注册执行器。 / Register the executor."""
    _run_standalone(ctx, "register")


@standalone_cli.command(name="remove")
@click.pass_context
def standalone_remove(ctx: click.Context) -> None:
    """注销执行器。 / Deregister the executor."""
    _run_standalone(ctx, "remove")


def main(args: Optional[List[str]] = None) -> None:
    """
    ``flask-xxljob`` 控制台脚本入口。

    Console-script entry point for ``flask-xxljob``.
    """
    standalone_cli.main(args=args if args is not None else sys.argv[1:], standalone_mode=True)


__all__ = ["xxljob_cli", "standalone_cli", "main"]

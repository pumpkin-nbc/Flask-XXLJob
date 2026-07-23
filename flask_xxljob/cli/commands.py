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
from ..status import XXLJobStatus


def _runtime() -> Any:
    runtime = current_app.extensions.get(EXTENSION_KEY)
    if runtime is None:
        raise click.ClickException(
            "Flask-XXLJob is not initialized on this application."
        )
    return runtime


def _build_status(runtime: Any) -> XXLJobStatus:
    config = runtime.config
    snapshot = runtime.registry_service.status_snapshot()
    return XXLJobStatus(
        enabled=config.enabled,
        auto_register=config.auto_register,
        registered=snapshot["registered"],
        last_registry_time=snapshot["last_registry_time"],
        last_registry_success=snapshot["last_registry_success"],
        last_registry_admin_address=snapshot["last_registry_admin_address"],
        last_registry_error_type=snapshot["last_registry_error_type"],
        last_registry_message=snapshot["last_registry_message"],
        registry_thread_running=snapshot["registry_thread_running"],
        log_enabled=runtime.log_manager.effective_enabled,
        log_level=runtime.log_manager.level,
        log_file_enabled=runtime.log_manager.file_enabled,
        log_console_enabled=runtime.log_manager.console_enabled,
        log_file=runtime.log_manager.log_file,
    )


def _echo_status(status: XXLJobStatus) -> None:
    # 只输出插件状态，绝不输出 Access Token 或业务任务信息。
    # Print plugin status only; never the access token or business-task info.
    click.echo("Flask-XXLJob status")
    click.echo(f"  Enabled: {status.enabled}")
    click.echo(f"  Auto register: {status.auto_register}")
    click.echo(f"  Registered: {status.registered}")
    click.echo(f"  Registry thread running: {status.registry_thread_running}")
    click.echo(f"  Log enabled: {status.log_enabled}")
    click.echo(f"  Log level: {status.log_level}")
    click.echo(f"  File logging: {status.log_file_enabled}")
    if status.log_file is not None:
        click.echo(f"  Log file: {status.log_file}")
    click.echo(f"  Console logging: {status.log_console_enabled}")
    if status.last_registry_time is None:
        click.echo("  Last registry: (no attempt yet)")
    else:
        click.echo(f"  Last registry time: {status.last_registry_time}")
        click.echo(f"  Last registry admin: {status.last_registry_admin_address}")
        result = "success" if status.last_registry_success else "failure"
        click.echo(f"  Last registry result: {result}")
        if not status.last_registry_success:
            click.echo(f"  Last registry error type: {status.last_registry_error_type}")
            click.echo(f"  Last registry message: {status.last_registry_message}")


def _status_failed(status: XXLJobStatus) -> bool:
    # 仅当确实发生过一次失败时才视为失败（未尝试过不算失败）。
    # Treat as failure only when an attempt actually failed (no attempt is ok).
    return status.last_registry_success is False


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


@xxljob_cli.command(name="status")
@with_appcontext
def status_command() -> None:
    """查询插件运行状态。 / Query the plugin runtime status."""
    status = _build_status(_runtime())
    _echo_status(status)
    if _status_failed(status):
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


@standalone_cli.command(name="status")
@click.pass_context
def standalone_status(ctx: click.Context) -> None:
    """查询插件运行状态。 / Query the plugin runtime status."""
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
        status = _build_status(runtime)
    _echo_status(status)
    if _status_failed(status):
        raise SystemExit(1)


def main(args: Optional[List[str]] = None) -> None:
    """
    ``flask-xxljob`` 控制台脚本入口。

    Console-script entry point for ``flask-xxljob``.
    """
    standalone_cli.main(args=args if args is not None else sys.argv[1:], standalone_mode=True)


__all__ = ["xxljob_cli", "standalone_cli", "main"]

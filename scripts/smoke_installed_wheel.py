"""Self-contained smoke test for an isolated installed Flask-XXLJob wheel."""

from __future__ import annotations

import argparse
import json
import site
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from typing import List, Optional
from unittest import mock

from click.testing import CliRunner
from flask import Flask
from flask.cli import ScriptInfo

import flask_xxljob
from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse
from flask_xxljob.cli.commands import standalone_cli, xxljob_cli


class AdminState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.paths: List[str] = []
        self.registry_event = threading.Event()
        self.remove_success = True

    def record(self, path: str) -> bool:
        with self.lock:
            self.paths.append(path)
            if path.endswith("/api/registry"):
                self.registry_event.set()
            return self.remove_success

    def count(self, suffix: str) -> int:
        with self.lock:
            return sum(path.endswith(suffix) for path in self.paths)


class AdminHandler(BaseHTTPRequestHandler):
    state: AdminState

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        remove_success = self.state.record(self.path)
        success = not self.path.endswith("/api/registryRemove") or remove_success
        body = json.dumps(
            {"code": 200 if success else 500, "msg": "ok" if success else "down"}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _assert_installed_import(source_root: Path) -> None:
    module_path = Path(flask_xxljob.__file__).resolve()
    site_paths = [Path(item).resolve() for item in site.getsitepackages()]
    assert any(_is_relative_to(module_path, item) for item in site_paths), module_path
    assert not _is_relative_to(module_path, source_root.resolve()), module_path
    assert flask_xxljob.__version__ == "0.4.0"
    assert version("Flask-XXLJob") == "0.4.0"


def _make_app(name: str, admin_url: str) -> tuple:
    app = Flask(name)
    app.config.update(
        TESTING=True,
        XXL_JOB_ADMIN_ADDRESSES=[admin_url],
        XXL_JOB_EXECUTOR_APP_NAME="installed-wheel-smoke",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
        XXL_JOB_AUTO_REGISTER=False,
        XXL_JOB_REGISTRY_INTERVAL=1,
    )
    extension = FlaskXXLJob(app)

    @extension.on_run("smoke")
    def _run(_request):
        return XXLJobResponse.success()

    @extension.on_idle_beat
    def _idle(_request):
        return XXLJobResponse.success()

    @extension.on_kill
    def _kill(_request):
        return XXLJobResponse.success()

    @extension.on_log
    def _log(request):
        return LogResponse(
            from_line_num=request.from_line_num,
            to_line_num=request.from_line_num,
            log_content="smoke",
            is_end=True,
        )

    return app, extension


def _assert_endpoints_and_callback(app: Flask, extension: FlaskXXLJob) -> None:
    client = app.test_client()
    requests = (
        ("/beat", None),
        ("/run", {"jobId": 1, "executorHandler": "smoke"}),
        ("/idleBeat", {"jobId": 1}),
        ("/kill", {"jobId": 1}),
        ("/log", {"logDateTim": 1, "logId": 1, "fromLineNum": 1}),
    )
    for path, payload in requests:
        response = client.post(path, json=payload)
        assert response.status_code == 200
        assert response.get_json()["code"] == 200
    assert extension.callback_success(1, 1, "smoke", app=app).success is True


def _script_info(app: Flask) -> ScriptInfo:
    info = ScriptInfo()
    info.load_app = lambda: app  # type: ignore[assignment]
    return info


def _invoke(kind: str, app: Flask, command: str):
    runner = CliRunner()
    if kind == "flask":
        return runner.invoke(xxljob_cli, [command], obj=_script_info(app))
    with mock.patch.object(ScriptInfo, "load_app", return_value=app):
        return runner.invoke(standalone_cli, [command])


def _assert_cli_remove_lifecycle(
    kind: str,
    remove_success: bool,
    scenario: int,
    admin_url: str,
    state: AdminState,
) -> None:
    app, extension = _make_app(
        f"installed_smoke_{kind}_{remove_success}_{scenario}", admin_url
    )
    runtime = app.extensions["xxljob"]
    state.remove_success = remove_success

    assert _invoke(kind, app, "register").exit_code == 0
    assert _invoke(kind, app, "status").exit_code == 0

    state.registry_event.clear()
    before_registry = state.count("/api/registry")
    extension.start_registry(app)
    assert state.registry_event.wait(3.0)
    assert state.count("/api/registry") > before_registry

    before_remove = state.count("/api/registryRemove")
    result = _invoke(kind, app, "remove")
    assert result.exit_code == (0 if remove_success else 1), result.output
    assert runtime.registry_service.is_running is False
    assert state.count("/api/registryRemove") == before_remove + 1

    calls_after_remove = state.count("/api/registry")
    time.sleep(runtime.config.registry_interval + 0.25)
    assert state.count("/api/registry") == calls_after_remove
    runtime.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args(argv)
    _assert_installed_import(args.source_root)

    state = AdminState()
    AdminHandler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", 0), AdminHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    admin_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        app, extension = _make_app("installed_smoke_protocol", admin_url)
        _assert_endpoints_and_callback(app, extension)
        app.extensions["xxljob"].close()

        scenario = 0
        for kind in ("flask", "standalone"):
            for remove_success in (True, False):
                scenario += 1
                _assert_cli_remove_lifecycle(
                    kind, remove_success, scenario, admin_url, state
                )
        assert CliRunner().invoke(standalone_cli, ["--version"]).exit_code == 0
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=3.0)
    print("Installed-wheel smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Extension initialization and isolation tests."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob, XXLJobResponse
from flask_xxljob.exceptions import (
    XXLJobAlreadyInitializedError,
    XXLJobConfigError,
    XXLJobError,
    XXLJobInitializationError,
)
from flask_xxljob.extension import EXTENSION_KEY
from tests.conftest import BASE_CONFIG, make_app


def test_lazy_init():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    assert EXTENSION_KEY in app.extensions


def test_direct_init():
    app = Flask("direct")
    app.config.update(BASE_CONFIG)
    ext = FlaskXXLJob(app)
    assert EXTENSION_KEY in app.extensions
    assert ext is not None


def test_runtime_stored_in_extensions(app_ext):
    app, _ = app_ext
    runtime = app.extensions[EXTENSION_KEY]
    assert runtime.config is not None
    assert runtime.callback_registry is not None
    assert runtime.admin_client is not None
    assert runtime.callback_client is not None
    assert runtime.registry_service is not None


def test_double_init_raises():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    with pytest.raises(XXLJobAlreadyInitializedError):
        ext.init_app(app)


def test_invalid_config_raises():
    app = Flask("bad")
    app.config.update(XXL_JOB_ADMIN_ADDRESSES=[])
    with pytest.raises(XXLJobConfigError):
        FlaskXXLJob(app)


def test_multiple_app_runtime_isolation():
    ext = FlaskXXLJob()
    app1, _ = make_app(ext, name="app1")

    @ext.on_run
    def run1(request):
        return XXLJobResponse.success(content="app1")

    app2, _ = make_app(ext, name="app2")

    def run2(request):
        return XXLJobResponse.failure("app2")

    ext.set_run_callback(app2, run2)

    r1 = app1.extensions[EXTENSION_KEY].callback_registry.run
    r2 = app2.extensions[EXTENSION_KEY].callback_registry.run
    assert r1 is run1
    assert r2 is run2
    assert r1 is not r2


def test_multiple_apps_require_explicit_app_or_context():
    ext = FlaskXXLJob()
    app1, _ = make_app(ext, name="ambiguous1")
    app2, _ = make_app(ext, name="ambiguous2")

    with pytest.raises(XXLJobError, match="Multiple Flask applications"):
        ext.get_status()

    assert ext.get_status(app1).enabled is True
    with app2.app_context():
        assert ext.get_status().enabled is True


def test_blueprint_registered(app_ext):
    app, _ = app_ext
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/run" in rules
    assert "/beat" in rules
    assert "/idleBeat" in rules
    assert "/kill" in rules
    assert "/log" in rules


def test_route_prefix_applied():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="prefixed", XXL_JOB_ROUTE_PREFIX="exec")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/exec/run" in rules


@pytest.mark.parametrize("prefix", ["/xxl-job", "/xxl-job/", "//xxl-job//"])
def test_route_prefix_variants_have_no_double_slash(prefix):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="pfx_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX=prefix)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/xxl-job/run" in rules
    assert not any("//" in rule for rule in rules)


def test_empty_route_prefix_mounts_at_root():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="root_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX="")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/run" in rules


def test_slash_route_prefix_mounts_at_root_and_returns_json_errors():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="slash_root_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX="/")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/run" in rules
    resp = app.test_client().get("/run")
    assert resp.is_json
    assert resp.json["code"] == 500


def test_prefixed_run_dispatches():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="pfxrun_" + str(id(ext)), XXL_JOB_ROUTE_PREFIX="/xxl-job/")

    @ext.on_run
    def handler(request):
        return XXLJobResponse.success(content="prefixed")

    resp = app.test_client().post("/xxl-job/run", json={"jobId": 1})
    assert resp.json["content"] == "prefixed"


def test_cli_command_registered(app_ext):
    app, _ = app_ext
    assert "xxljob" in app.cli.commands


@pytest.mark.parametrize("path", ["/beat", "/idleBeat", "/run", "/kill", "/log"])
def test_post_route_conflict_fails_without_partial_initialization(path):
    app = Flask("conflict_" + path.strip("/"))
    app.config.update(BASE_CONFIG)
    app.add_url_rule(path, endpoint="host", view_func=lambda: "host", methods=["POST"])

    with pytest.raises(XXLJobInitializationError, match=path):
        FlaskXXLJob(app)

    assert EXTENSION_KEY not in app.extensions
    assert "xxljob" not in app.cli.commands
    assert not any(name.startswith("xxljob_") for name in app.blueprints)


def test_prefixed_post_route_conflict_fails():
    app = Flask("prefixed_conflict")
    app.config.update(BASE_CONFIG, XXL_JOB_ROUTE_PREFIX="/executor")
    app.add_url_rule(
        "/executor/run", endpoint="host_run", view_func=lambda: "host", methods=["POST"]
    )

    with pytest.raises(XXLJobInitializationError, match="/executor/run"):
        FlaskXXLJob(app)


def test_get_only_host_route_does_not_conflict():
    app = Flask("get_only")
    app.config.update(BASE_CONFIG)
    app.add_url_rule("/run", endpoint="host_get", view_func=lambda: "host", methods=["GET"])

    FlaskXXLJob(app)

    assert app.test_client().get("/run").data == b"host"


def test_disabled_extension_does_not_check_route_conflicts():
    app = Flask("disabled_conflict")
    app.config.update(BASE_CONFIG, XXL_JOB_ENABLED=False)
    app.add_url_rule("/run", endpoint="host_run", view_func=lambda: "host", methods=["POST"])

    FlaskXXLJob(app)

    assert EXTENSION_KEY in app.extensions
    run_rules = [rule for rule in app.url_map.iter_rules() if rule.rule == "/run"]
    assert len(run_rules) == 1

"""Callback registration pattern tests (0.1.1)."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob, XXLJobResponse
from flask_xxljob.exceptions import XXLJobError
from tests.conftest import BASE_CONFIG


def make_app(ext, name):
    app = Flask(name)
    app.config.update(dict(BASE_CONFIG))
    ext.init_app(app)
    return app


def test_module_level_registration_before_init_app():
    # 形式 1：在 init_app 之前用装饰器注册（模块级）。
    # Form 1: register with a decorator before init_app (module level).
    ext = FlaskXXLJob()

    @ext.on_run("demoJobHandler")
    def handler(request):
        return XXLJobResponse.success(content="deferred")

    app = make_app(ext, "pre_init")
    resp = app.test_client().post(
        "/run", json={"jobId": 1, "executorHandler": "demoJobHandler"}
    )
    assert resp.json["code"] == 200
    assert resp.json["content"] == "deferred"


def test_in_factory_registration_after_init_app():
    # 形式 2：init_app 之后注册。 / Form 2: register after init_app.
    ext = FlaskXXLJob()
    app = make_app(ext, "post_init")

    @ext.on_run("demoJobHandler")
    def handler(request):
        return XXLJobResponse.success(content="post")

    resp = app.test_client().post(
        "/run", json={"jobId": 1, "executorHandler": "demoJobHandler"}
    )
    assert resp.json["content"] == "post"


def test_duplicate_registration_raises():
    ext = FlaskXXLJob()

    @ext.on_run("demoJobHandler")
    def handler(request):
        return XXLJobResponse.success()

    with pytest.raises(XXLJobError):
        @ext.on_run("demoJobHandler")
        def handler2(request):
            return XXLJobResponse.success()


def test_per_app_isolation_with_separate_extensions():
    ext_a = FlaskXXLJob()
    ext_b = FlaskXXLJob()

    @ext_a.on_run("demoJobHandler")
    def handler_a(request):
        return XXLJobResponse.success(content="A")

    @ext_b.on_run("demoJobHandler")
    def handler_b(request):
        return XXLJobResponse.success(content="B")

    app_a = make_app(ext_a, "iso_a")
    app_b = make_app(ext_b, "iso_b")

    payload = {"jobId": 1, "executorHandler": "demoJobHandler"}
    assert app_a.test_client().post("/run", json=payload).json["content"] == "A"
    assert app_b.test_client().post("/run", json=payload).json["content"] == "B"

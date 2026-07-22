"""Protocol error-handling tests: unified JSON responses (0.1.1)."""

from __future__ import annotations

from flask_xxljob import FlaskXXLJob, XXLJobResponse
from tests.conftest import make_app


def build(**overrides):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="err_" + str(id(ext)), **overrides)

    @ext.on_run
    def handler(request):
        return XXLJobResponse.success()

    return app, ext


def test_empty_body_returns_json_failure():
    app, _ = build()
    resp = app.test_client().post("/run", data=b"")
    assert resp.json["code"] == 500
    assert "empty" in resp.json["msg"]


def test_non_json_body_returns_json_failure():
    app, _ = build()
    resp = app.test_client().post(
        "/run", data=b"{not json", content_type="application/json"
    )
    assert resp.json["code"] == 500
    assert "invalid JSON" in resp.json["msg"]


def test_array_body_rejected():
    app, _ = build()
    resp = app.test_client().post(
        "/run", data=b"[1,2,3]", content_type="application/json"
    )
    assert resp.json["code"] == 500
    assert "JSON object" in resp.json["msg"]


def test_bad_numeric_field_returns_failure():
    app, _ = build()
    resp = app.test_client().post("/run", json={"jobId": "abc"})
    assert resp.json["code"] == 500
    assert "jobId" in resp.json["msg"]


def test_zero_numeric_is_accepted():
    app, _ = build()
    resp = app.test_client().post("/run", json={"jobId": 0})
    assert resp.json["code"] == 200


def test_unsupported_return_type_is_failure():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="unsup_" + str(id(ext)))

    @ext.on_run
    def handler(request):
        return {"not": "a response"}

    resp = app.test_client().post("/run", json={"jobId": 1})
    assert resp.json["code"] == 500
    assert "unsupported response type" in resp.json["msg"]


def test_none_return_type_is_failure():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="none_" + str(id(ext)))

    @ext.on_run
    def handler(request):
        return None

    resp = app.test_client().post("/run", json={"jobId": 1})
    assert resp.json["code"] == 500
    assert "unsupported response type" in resp.json["msg"]


def test_wrong_method_returns_json_not_html():
    app, _ = build()
    resp = app.test_client().get("/run")
    assert resp.content_type.startswith("application/json")
    assert resp.json["code"] == 500


def test_non_executor_404_stays_default():
    app, _ = build()
    resp = app.test_client().post("/definitely-not-a-route")
    # 非执行器路径保持 Flask 默认行为。
    # Non-executor paths keep Flask's default behavior.
    assert resp.status_code == 404

"""Protocol error-handling tests: unified JSON responses (0.1.1)."""

from __future__ import annotations

from flask import Flask, jsonify

from flask_xxljob import FlaskXXLJob, XXLJobResponse
from tests.conftest import BASE_CONFIG, make_app


def build(**overrides):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="err_" + str(id(ext)), **overrides)

    @ext.on_run("demoJobHandler")
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
    resp = app.test_client().post(
        "/run", json={"jobId": 0, "executorHandler": "demoJobHandler"}
    )
    assert resp.json["code"] == 200


def test_unsupported_return_type_is_failure():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="unsup_" + str(id(ext)))

    @ext.on_run("demoJobHandler")
    def handler(request):
        return {"not": "a response"}

    resp = app.test_client().post(
        "/run", json={"jobId": 1, "executorHandler": "demoJobHandler"}
    )
    assert resp.json["code"] == 500
    assert "unsupported response type" in resp.json["msg"]


def test_none_return_type_is_failure():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="none_" + str(id(ext)))

    @ext.on_run("demoJobHandler")
    def handler(request):
        return None

    resp = app.test_client().post(
        "/run", json={"jobId": 1, "executorHandler": "demoJobHandler"}
    )
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


def test_host_custom_404_and_405_handlers_are_preserved():
    ext = FlaskXXLJob()
    app = Flask("host_errors_" + str(id(ext)))
    app.config.update(BASE_CONFIG)

    @app.post("/host-only-post")
    def host_only_post():
        return "ok"

    @app.errorhandler(404)
    def custom_404(error):
        return jsonify(source="host", code=404), 404

    @app.errorhandler(405)
    def custom_405(error):
        return jsonify(source="host", code=405), 405

    # Initialize after the host handlers exist. The extension must not replace
    # them, while its own endpoint routing failures must still use XXL-JOB JSON.
    ext.init_app(app)

    client = app.test_client()
    not_found = client.get("/missing")
    wrong_method = client.get("/host-only-post")
    executor_wrong_method = client.get("/run")

    assert not_found.status_code == 404
    assert not_found.json == {"source": "host", "code": 404}
    assert wrong_method.status_code == 405
    assert wrong_method.json == {"source": "host", "code": 405}
    assert executor_wrong_method.status_code == 200
    assert executor_wrong_method.json["code"] == 500


def test_content_type_with_charset_is_parsed():
    app, _ = build()
    resp = app.test_client().post(
        "/run",
        data=b'{"jobId": 5, "executorHandler": "demoJobHandler"}',
        content_type="application/json; charset=UTF-8",
    )
    assert resp.json["code"] == 200


def test_chinese_executor_params_parsed():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="zh_" + str(id(ext)))
    seen = {}

    @ext.on_run("demoJobHandler")
    def handler(request):
        seen["params"] = request.executor_params
        return XXLJobResponse.success()

    resp = app.test_client().post(
        "/run",
        data=(
            '{"jobId": 1, "executorHandler": "demoJobHandler", '
            '"executorParams": "\u4efb\u52a1\u53c2\u6570"}'
        ).encode("utf-8"),
        content_type="application/json; charset=UTF-8",
    )
    assert resp.json["code"] == 200
    assert seen["params"] == "\u4efb\u52a1\u53c2\u6570"

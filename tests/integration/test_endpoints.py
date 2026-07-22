"""Executor endpoint tests (/beat, /run, /idleBeat, /kill, /log)."""

from __future__ import annotations

import threading

from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse
from flask_xxljob.client import ACCESS_TOKEN_HEADER
from tests.conftest import make_app


def build(**overrides):
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="ep_" + str(id(ext)), **overrides)
    return app, ext


# ----------------------------- /beat -----------------------------

def test_beat_success():
    app, _ = build()
    resp = app.test_client().post("/beat")
    assert resp.json == {"code": 200, "msg": None, "content": None}


def test_beat_no_callback_required():
    app, _ = build()
    assert app.test_client().post("/beat").json["code"] == 200


def test_beat_token_ok():
    app, _ = build(XXL_JOB_ACCESS_TOKEN="tok")
    resp = app.test_client().post("/beat", headers={ACCESS_TOKEN_HEADER: "tok"})
    assert resp.json["code"] == 200


def test_beat_token_wrong():
    app, _ = build(XXL_JOB_ACCESS_TOKEN="tok")
    resp = app.test_client().post("/beat", headers={ACCESS_TOKEN_HEADER: "bad"})
    assert resp.json["code"] == 500
    assert resp.json["msg"] == "The access token is wrong."


# ----------------------------- /run -----------------------------

def test_run_dispatches_and_parses():
    app, ext = build()
    seen = {}

    @ext.on_run
    def handler(request):
        seen["job_id"] = request.job_id
        seen["params"] = request.parse_params()
        return XXLJobResponse.success()

    resp = app.test_client().post(
        "/run", json={"jobId": 9, "executorParams": '{"k": 1}', "logId": 3}
    )
    assert resp.json["code"] == 200
    assert seen["job_id"] == 9
    assert seen["params"] == {"k": 1}


def test_run_failure_result():
    app, ext = build()

    @ext.on_run
    def handler(request):
        return XXLJobResponse.failure("submit task failed")

    resp = app.test_client().post("/run", json={"jobId": 1})
    assert resp.json["code"] == 500
    assert resp.json["msg"] == "submit task failed"


def test_run_unconfigured():
    app, _ = build()
    resp = app.test_client().post("/run", json={"jobId": 1})
    assert resp.json["msg"] == "XXL-JOB run callback is not configured"


def test_run_handler_exception():
    app, ext = build()

    @ext.on_run
    def handler(request):
        raise RuntimeError("boom")

    resp = app.test_client().post("/run", json={"jobId": 1})
    assert resp.json["code"] == 500
    assert resp.json["msg"] == "XXL-JOB run callback execution failed"


def test_run_missing_fields_defaults():
    app, ext = build()

    @ext.on_run
    def handler(request):
        assert request.job_id == 0
        assert request.executor_params == ""
        return XXLJobResponse.success()

    assert app.test_client().post("/run", json={}).json["code"] == 200


def test_run_oversized_params_rejected():
    app, ext = build(XXL_JOB_MAX_PARAM_LENGTH=10)

    @ext.on_run
    def handler(request):
        return XXLJobResponse.success()

    resp = app.test_client().post("/run", json={"executorParams": "x" * 50})
    assert resp.json["code"] == 500
    assert "executorParams" in resp.json["msg"]


def test_run_token_validation():
    app, ext = build(XXL_JOB_ACCESS_TOKEN="tok")

    @ext.on_run
    def handler(request):
        return XXLJobResponse.success()

    bad = app.test_client().post("/run", json={"jobId": 1})
    assert bad.json["code"] == 500
    ok = app.test_client().post(
        "/run", json={"jobId": 1}, headers={ACCESS_TOKEN_HEADER: "tok"}
    )
    assert ok.json["code"] == 200


def test_run_does_not_spawn_threads():
    app, ext = build()
    before = threading.active_count()

    @ext.on_run
    def handler(request):
        return XXLJobResponse.success()

    app.test_client().post("/run", json={"jobId": 1})
    assert threading.active_count() == before


def test_run_does_not_auto_callback(mocker):
    app, ext = build()
    post = mocker.patch("flask_xxljob.client.requests.post")

    @ext.on_run
    def handler(request):
        return XXLJobResponse.success()

    app.test_client().post("/run", json={"jobId": 1})
    post.assert_not_called()


# --------------------------- /idleBeat ---------------------------

def test_idle_beat_idle_and_busy():
    app, ext = build()

    @ext.on_idle_beat
    def handler(request):
        if request.job_id == 1:
            return XXLJobResponse.success()
        return XXLJobResponse.failure("job is running")

    assert app.test_client().post("/idleBeat", json={"jobId": 1}).json["code"] == 200
    assert app.test_client().post("/idleBeat", json={"jobId": 2}).json["code"] == 500


def test_idle_beat_unconfigured():
    app, _ = build()
    resp = app.test_client().post("/idleBeat", json={"jobId": 1})
    assert resp.json["msg"] == "XXL-JOB idleBeat callback is not configured"


def test_idle_beat_exception():
    app, ext = build()

    @ext.on_idle_beat
    def handler(request):
        raise ValueError("x")

    assert app.test_client().post("/idleBeat", json={"jobId": 1}).json["code"] == 500


# ----------------------------- /kill -----------------------------

def test_kill_success_and_failure():
    app, ext = build()

    @ext.on_kill
    def handler(request):
        return XXLJobResponse.success() if request.job_id == 1 else XXLJobResponse.failure(
            "kill task failed"
        )

    assert app.test_client().post("/kill", json={"jobId": 1}).json["code"] == 200
    assert app.test_client().post("/kill", json={"jobId": 2}).json["code"] == 500


def test_kill_unconfigured():
    app, _ = build()
    resp = app.test_client().post("/kill", json={"jobId": 1})
    assert resp.json["msg"] == "XXL-JOB kill callback is not configured"


def test_kill_exception():
    app, ext = build()

    @ext.on_kill
    def handler(request):
        raise RuntimeError("x")

    assert app.test_client().post("/kill", json={"jobId": 1}).json["code"] == 500


# ----------------------------- /log ------------------------------

def test_log_conversion():
    app, ext = build()

    @ext.on_log
    def handler(request):
        return LogResponse(
            from_line_num=request.from_line_num,
            to_line_num=request.from_line_num + 2,
            log_content="line",
            is_end=True,
        )

    resp = app.test_client().post(
        "/log", json={"logDateTim": 1, "logId": 2, "fromLineNum": 5}
    )
    assert resp.json["code"] == 200
    assert resp.json["content"] == {
        "fromLineNum": 5,
        "toLineNum": 7,
        "logContent": "line",
        "isEnd": True,
    }


def test_log_unconfigured():
    app, _ = build()
    resp = app.test_client().post("/log", json={"logId": 1})
    assert resp.json["msg"] == "XXL-JOB log callback is not configured"


def test_log_exception():
    app, ext = build()

    @ext.on_log
    def handler(request):
        raise RuntimeError("x")

    assert app.test_client().post("/log", json={"logId": 1}).json["code"] == 500

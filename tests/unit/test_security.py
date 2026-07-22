"""Access-token comparison and request-limit security tests (0.2.0)."""

from __future__ import annotations

from flask_xxljob import FlaskXXLJob
from flask_xxljob.protocol.validator import check_access_token
from tests.conftest import make_app


def test_no_token_configured_passes():
    assert check_access_token("", None) is True
    assert check_access_token("   ", "anything") is True


def test_correct_token_passes():
    assert check_access_token("tok", "tok") is True


def test_wrong_token_rejected():
    assert check_access_token("tok", "nope") is False


def test_missing_token_rejected():
    assert check_access_token("tok", None) is False


def test_non_string_token_rejected():
    assert check_access_token("tok", 12345) is False  # type: ignore[arg-type]
    assert check_access_token("tok", b"tok") is False  # type: ignore[arg-type]


def test_unicode_token_supported():
    assert check_access_token("令牌", "令牌") is True
    assert check_access_token("令牌", "令") is False


def test_token_not_in_endpoint_response():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, XXL_JOB_ACCESS_TOKEN="secret-token")
    resp = app.test_client().post(
        "/run",
        json={"jobId": 1},
        headers={"XXL-JOB-ACCESS-TOKEN": "wrong"},
    )
    assert "secret-token" not in resp.get_data(as_text=True)


def test_body_over_limit_returns_json():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, XXL_JOB_MAX_REQUEST_SIZE=10)
    ext.set_run_callback(app, lambda r: None)
    resp = app.test_client().post(
        "/run", data=b'{"jobId": 123456789012345}', content_type="application/json"
    )
    assert resp.is_json
    assert resp.json["code"] == 500


def test_param_over_limit_returns_json():
    from flask_xxljob import XXLJobResponse

    ext = FlaskXXLJob()
    app, _ = make_app(ext, XXL_JOB_MAX_PARAM_LENGTH=3)
    ext.set_run_callback(app, lambda r: XXLJobResponse.success())
    resp = app.test_client().post(
        "/run", json={"jobId": 1, "executorParams": "toolong"}
    )
    assert resp.is_json
    assert resp.json["code"] == 500


def test_chinese_param_length_counts_characters():
    from flask_xxljob import XXLJobResponse

    ext = FlaskXXLJob()
    app, _ = make_app(ext, XXL_JOB_MAX_PARAM_LENGTH=3)
    ext.set_run_callback(app, lambda r: XXLJobResponse.success())
    # 3 Chinese characters -> within limit (measured in characters).
    ok = app.test_client().post("/run", json={"jobId": 1, "executorParams": "参数值"})
    assert ok.json["code"] == 200
    # 4 characters -> over limit.
    bad = app.test_client().post("/run", json={"jobId": 1, "executorParams": "参数值多"})
    assert bad.json["code"] == 500

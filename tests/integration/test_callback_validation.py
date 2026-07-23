"""Task-result callback ergonomics and validation tests (0.1.1)."""

from __future__ import annotations

import pytest

from flask_xxljob import FlaskXXLJob
from flask_xxljob.exceptions import XXLJobRequestError, XXLJobValidationError
from tests.conftest import make_app


class FakeResponse:
    status_code = 200

    def json(self):
        return {"code": 200, "msg": None, "content": None}


def build():
    ext = FlaskXXLJob()
    app, _ = make_app(ext, name="cb_" + str(id(ext)))
    return app, ext


def test_callback_message_none_defaults_to_empty(mocker):
    app, ext = build()
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    with app.app_context():
        ext.callback_success(log_id=1, log_date_time=2)
    payload = post.call_args.kwargs["json"]
    assert payload[0]["handleMsg"] == ""


def test_callback_unicode_message(mocker):
    app, ext = build()
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    with app.app_context():
        ext.callback_failure(log_id=1, log_date_time=2, message="任务失败-\u2764")
    payload = post.call_args.kwargs["json"]
    assert payload[0]["handleMsg"] == "任务失败-\u2764"


def test_callback_rejects_bool_log_id(mocker):
    app, ext = build()
    mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    with app.app_context():
        with pytest.raises(XXLJobRequestError):
            ext.callback(log_id=True, log_date_time=2, handle_code=200)


def test_callback_rejects_non_int_log_date_time(mocker):
    app, ext = build()
    mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    with app.app_context():
        with pytest.raises(XXLJobRequestError):
            ext.callback(log_id=1, log_date_time="2", handle_code=200)


def test_callback_backward_compatible_handle_msg_keyword(mocker):
    # 0.1.0 的 handle_msg 关键字用法仍然有效。
    # The 0.1.0 handle_msg keyword usage still works.
    app, ext = build()
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    with app.app_context():
        ext.callback(log_id=1, log_date_time=2, handle_code=200, handle_msg="done")
    payload = post.call_args.kwargs["json"]
    assert payload[0]["handleMsg"] == "done"


@pytest.mark.parametrize("handle_msg", [1, True, [], {}])
def test_callback_rejects_non_string_handle_msg_without_sending(
    mocker, handle_msg
):
    app, ext = build()
    post = mocker.patch("flask_xxljob.client.requests.post")

    with app.app_context():
        with pytest.raises(XXLJobValidationError, match="handle_msg.*must be a string"):
            ext.callback(
                log_id=1,
                log_date_time=2,
                handle_code=200,
                handle_msg=handle_msg,
            )

    post.assert_not_called()

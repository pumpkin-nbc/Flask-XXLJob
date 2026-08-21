"""Task-result callback ergonomics and validation tests (0.1.1)."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob
from flask_xxljob.exceptions import (
    XXLJobError,
    XXLJobRequestError,
    XXLJobValidationError,
)
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


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        ("callback", (1, 2, 200), {"handle_msg": None}),
        ("callback", (True, "2", False), {"handle_msg": {}}),
        ("callback", ("1", None, 200.0), {"handle_msg": []}),
        ("callback_success", (True, None), {"message": 123}),
        ("callback_success", ("1", 2.0), {"message": {}}),
        ("callback_failure", (None, False), {"message": []}),
        ("callback_failure", (1.0, "2"), {"message": None}),
    ],
)
def test_disabled_single_callbacks_skip_payload_validation(
    mocker, method, args, kwargs
):
    app, ext = make_app(
        name="disabled_single_{}".format(method),
        XXL_JOB_ENABLED=False,
    )
    post = mocker.patch("flask_xxljob.client.requests.post")

    result = getattr(ext, method)(*args, app=app, **kwargs)

    assert result.success is False
    assert result.error == "Flask-XXLJob is disabled."
    assert result.error_type == "config"
    assert result.attempt_count == 0
    post.assert_not_called()
    app.extensions["xxljob"].close()


@pytest.mark.parametrize(
    "callbacks",
    [
        [],
        [{}],
        ["not-a-callback"],
        [{"log_id": True, "log_date_time": None, "handle_msg": {}}],
        [
            {"log_id": index, "log_date_time": index}
            for index in range(101)
        ],
    ],
)
def test_disabled_callback_many_skips_batch_validation(mocker, callbacks):
    app, ext = make_app(
        name="disabled_many_{}".format(len(callbacks)),
        XXL_JOB_ENABLED=False,
    )
    post = mocker.patch("flask_xxljob.client.requests.post")

    result = ext.callback_many(callbacks, app=app)

    assert result.success is False
    assert result.error == "Flask-XXLJob is disabled."
    assert result.error_type == "config"
    assert result.attempt_count == 0
    post.assert_not_called()
    app.extensions["xxljob"].close()


def test_disabled_callback_still_requires_a_resolved_runtime():
    ext = FlaskXXLJob()

    with pytest.raises(XXLJobError, match="No Flask application available"):
        ext.callback(True, None, False)

    uninitialized = Flask("disabled_uninitialized")
    with pytest.raises(XXLJobError, match="not initialized"):
        ext.callback(True, None, False, app=uninitialized)

    with pytest.raises(XXLJobError, match="not initialized"):
        ext.callback(True, None, False, app=object())


def test_disabled_callback_does_not_hide_multi_app_ambiguity():
    ext = FlaskXXLJob()
    app_a, _ = make_app(
        ext,
        name="disabled_ambiguous_a",
        XXL_JOB_ENABLED=False,
    )
    app_b, _ = make_app(
        ext,
        name="disabled_ambiguous_b",
        XXL_JOB_ENABLED=False,
    )

    with pytest.raises(XXLJobError, match="Multiple Flask applications"):
        ext.callback(True, None, False)

    app_a.extensions["xxljob"].close()
    app_b.extensions["xxljob"].close()


def test_callback_disabled_state_is_isolated_per_target_runtime(mocker):
    ext = FlaskXXLJob()
    disabled_app, _ = make_app(
        ext,
        name="callback_isolation_disabled",
        XXL_JOB_ENABLED=False,
    )
    enabled_app, _ = make_app(
        ext,
        name="callback_isolation_enabled",
        XXL_JOB_ENABLED=True,
    )
    post = mocker.patch("flask_xxljob.client.requests.post")

    disabled = ext.callback(True, None, False, handle_msg={}, app=disabled_app)
    assert disabled.error_type == "config"

    with pytest.raises(XXLJobValidationError, match="log_id must be an integer"):
        ext.callback(True, None, False, handle_msg={}, app=enabled_app)

    post.assert_not_called()
    disabled_app.extensions["xxljob"].close()
    enabled_app.extensions["xxljob"].close()


def test_callback_only_mode_sends_callback_without_registry_or_remove(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(),
    )
    app, ext = make_app(
        name="callback_only",
        XXL_JOB_ENABLED=True,
        XXL_JOB_AUTO_REGISTER=False,
        XXL_JOB_DEREGISTER_ON_EXIT=False,
    )

    assert post.call_count == 0
    result = ext.callback_success(1, 2, "done", app=app)
    assert result.success is True
    assert post.call_count == 1
    assert post.call_args.args[0].endswith("/api/callback")

    app.extensions["xxljob"].close()
    assert post.call_count == 1

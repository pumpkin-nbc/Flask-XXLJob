"""Callback client tests."""

from __future__ import annotations

import requests

from flask_xxljob.client import ACCESS_TOKEN_HEADER
from flask_xxljob.client.callback_client import CALLBACK_PATH, CallbackClient
from flask_xxljob.config import XXLJobConfig


def make_config(**overrides):
    mapping = {
        "XXL_JOB_ADMIN_ADDRESSES": ["http://a:8080", "http://b:8080"],
        "XXL_JOB_EXECUTOR_APP_NAME": "app",
        "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
    }
    mapping.update(overrides)
    return XXLJobConfig.from_mapping(mapping)


class FakeResponse:
    def __init__(self, code=200, status_code=200):
        self.status_code = status_code
        self._code = code

    def json(self):
        return {"code": self._code, "msg": None, "content": None}


def test_callback_success_maps_official_fields(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config())
    result = client.callback(log_id=1, log_date_time=2, handle_code=200, handle_msg="ok")

    assert result.success is True
    args, kwargs = post.call_args
    assert args[0].endswith(CALLBACK_PATH)
    payload = kwargs["json"]
    assert isinstance(payload, list) and len(payload) == 1
    assert payload[0] == {"logId": 1, "logDateTim": 2, "handleCode": 200, "handleMsg": "ok"}


def test_callback_includes_token_header(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config(XXL_JOB_ACCESS_TOKEN="secret"))
    client.callback(log_id=1, log_date_time=2, handle_code=500, handle_msg="fail")
    headers = post.call_args.kwargs["headers"]
    assert headers[ACCESS_TOKEN_HEADER] == "secret"


def test_callback_omits_token_header_when_empty(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config())
    client.callback(log_id=1, log_date_time=2, handle_code=200)
    headers = post.call_args.kwargs["headers"]
    assert ACCESS_TOKEN_HEADER not in headers


def test_callback_message_truncated(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config(XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH=5))
    client.callback(log_id=1, log_date_time=2, handle_code=200, handle_msg="0123456789")
    payload = post.call_args.kwargs["json"]
    assert payload[0]["handleMsg"] == "01234"


def test_callback_failover_to_second_admin(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[requests.ConnectionError("down"), FakeResponse()],
    )
    client = CallbackClient(make_config())
    result = client.callback(log_id=1, log_date_time=2, handle_code=200)
    assert result.success is True
    assert result.address == "http://b:8080"
    assert post.call_count == 2


def test_callback_timeout_returns_failure(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.Timeout("timeout"),
    )
    client = CallbackClient(make_config(XXL_JOB_ADMIN_ADDRESSES=["http://a:8080"]))
    result = client.callback(log_id=1, log_date_time=2, handle_code=200)
    assert result.success is False
    assert "Timeout" in (result.error or "")


def test_callback_timeout_result_has_timeout_error_type(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.Timeout("timeout"),
    )
    client = CallbackClient(make_config(XXL_JOB_ADMIN_ADDRESSES=["http://a:8080"]))
    result = client.callback(log_id=1, log_date_time=2, handle_code=200)
    assert result.success is False
    assert result.error_type == "timeout"


def test_callback_business_failure_has_business_error_type(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(code=500),
    )
    client = CallbackClient(make_config(XXL_JOB_ADMIN_ADDRESSES=["http://a:8080"]))
    result = client.callback(log_id=1, log_date_time=2, handle_code=200)
    assert result.success is False
    assert result.error_type == "business"


def test_callback_uses_configured_timeout(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(
        make_config(XXL_JOB_HTTP_CONNECT_TIMEOUT=2, XXL_JOB_HTTP_READ_TIMEOUT=7)
    )
    client.callback(log_id=1, log_date_time=2, handle_code=200)
    assert post.call_args.kwargs["timeout"] == (2, 7)

"""Batch callback tests (0.2.0)."""

from __future__ import annotations

import pytest

from flask_xxljob import CallbackRequest
from flask_xxljob.client.callback_client import CALLBACK_PATH, CallbackClient
from flask_xxljob.config import XXLJobConfig
from flask_xxljob.exceptions import XXLJobValidationError


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


def test_single_callback_uses_batch_path(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config())
    result = client.callback(log_id=1, log_date_time=2, handle_code=200, handle_msg="ok")
    assert result.success is True
    payload = post.call_args.kwargs["json"]
    assert isinstance(payload, list) and len(payload) == 1
    assert payload[0] == {"logId": 1, "logDateTim": 2, "handleCode": 200, "handleMsg": "ok"}


def test_callback_many_sends_official_array(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config())
    result = client.callback_many(
        [
            CallbackRequest(log_id=1, log_date_time=10, handle_code=200, handle_msg="a"),
            CallbackRequest(log_id=2, log_date_time=20, handle_code=500, handle_msg="b"),
        ]
    )
    assert result.success is True
    assert post.call_args.args[0].endswith(CALLBACK_PATH)
    payload = post.call_args.kwargs["json"]
    assert len(payload) == 2
    assert payload[0]["logId"] == 1 and payload[1]["logId"] == 2


def test_callback_many_accepts_dicts(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config())
    client.callback_many([{"log_id": 5, "log_date_time": 6}])
    payload = post.call_args.kwargs["json"]
    assert payload[0] == {"logId": 5, "logDateTim": 6, "handleCode": 200, "handleMsg": ""}


def test_callback_many_empty_raises(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post")
    client = CallbackClient(make_config())
    with pytest.raises(XXLJobValidationError):
        client.callback_many([])
    post.assert_not_called()


def test_callback_many_over_limit_raises_no_send(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post")
    client = CallbackClient(make_config(XXL_JOB_CALLBACK_BATCH_MAX_SIZE=2))
    items = [CallbackRequest(log_id=i, log_date_time=i) for i in range(3)]
    with pytest.raises(XXLJobValidationError):
        client.callback_many(items)
    post.assert_not_called()


def test_callback_many_invalid_item_rejects_whole_batch(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post")
    client = CallbackClient(make_config())
    items = [
        CallbackRequest(log_id=1, log_date_time=2),
        CallbackRequest(log_id=True, log_date_time=2),  # bool rejected
    ]
    with pytest.raises(XXLJobValidationError):
        client.callback_many(items)
    post.assert_not_called()


def test_callback_many_bad_type_raises(mocker):
    mocker.patch("flask_xxljob.client.requests.post")
    client = CallbackClient(make_config())
    with pytest.raises(XXLJobValidationError):
        client.callback_many(["not-a-request"])


def test_callback_many_chinese_and_truncation(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = CallbackClient(make_config(XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH=3))
    client.callback_many(
        [CallbackRequest(log_id=1, log_date_time=2, handle_msg="任务执行完成")]
    )
    payload = post.call_args.kwargs["json"]
    # Unicode-safe truncation counts characters, not bytes.
    assert payload[0]["handleMsg"] == "任务执"


def test_callback_many_failover_on_network(mocker):
    import requests

    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[requests.ConnectionError("x"), FakeResponse()],
    )
    client = CallbackClient(make_config())
    result = client.callback_many([CallbackRequest(log_id=1, log_date_time=2)])
    assert result.success is True
    assert result.address == "http://b:8080"
    assert post.call_count == 2


def test_callback_many_business_failure_no_duplicate(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[FakeResponse(code=500), FakeResponse(code=200)],
    )
    client = CallbackClient(make_config())
    result = client.callback_many([CallbackRequest(log_id=1, log_date_time=2)])
    # Default: no business failover -> stops on first business response.
    assert result.success is False
    assert post.call_count == 1

"""Admin call retry/failover policy tests (0.2.0)."""

from __future__ import annotations

import requests

from flask_xxljob.client import (
    ERROR_BUSINESS,
    ERROR_INVALID_JSON,
    ERROR_TIMEOUT,
    post_to_admins,
)
from flask_xxljob.client.policy import (
    RETRY_BACKOFF_CAP,
    RETRY_COUNT_CAP,
    AdminCallPolicy,
)
from flask_xxljob.config import XXLJobConfig


class FakeResponse:
    def __init__(self, code=200, status_code=200, bad_json=False):
        self.status_code = status_code
        self._code = code
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("no json")
        return {"code": self._code, "msg": "m"}


def test_default_policy_no_retry(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.ConnectionError("x"),
    )
    result = post_to_admins(
        ["http://a:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(),
    )
    assert result.success is False
    assert post.call_count == 1
    assert result.attempt_count == 1


def test_retry_on_network_then_success(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[requests.ConnectionError("x"), FakeResponse()],
    )
    sleep = mocker.patch("flask_xxljob.client.time.sleep")
    result = post_to_admins(
        ["http://a:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(retry_count=2, retry_backoff=0.5),
    )
    assert result.success is True
    assert result.attempt_count == 2
    sleep.assert_called_once_with(0.5)


def test_retry_exhausted(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.Timeout("t"),
    )
    mocker.patch("flask_xxljob.client.time.sleep")
    result = post_to_admins(
        ["http://a:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(retry_count=2),
    )
    assert result.success is False
    assert result.error_type == ERROR_TIMEOUT
    assert result.attempt_count == 3  # 1 + 2 retries


def test_failover_to_next_admin_on_network(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[requests.ConnectionError("x"), FakeResponse()],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(),
    )
    assert result.success is True
    assert result.address == "http://b:8080"
    assert post.call_count == 2


def test_business_error_no_failover_by_default(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[FakeResponse(code=500), FakeResponse(code=200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(),
    )
    assert result.success is False
    assert result.error_type == ERROR_BUSINESS
    assert post.call_count == 1


def test_invalid_json_no_failover_by_default(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[FakeResponse(bad_json=True), FakeResponse(code=200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(),
    )
    assert result.success is False
    assert result.error_type == ERROR_INVALID_JSON
    assert post.call_count == 1


def test_non_object_json_failover_when_enabled(mocker):
    non_object = FakeResponse()
    non_object.json = lambda: []
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[non_object, FakeResponse(code=200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"],
        "/api/registry",
        {},
        "",
        (3, 5),
        policy=AdminCallPolicy(failover_on_invalid_json=True),
    )
    assert result.success is True
    assert result.address == "http://b:8080"
    assert post.call_count == 2


def test_business_failover_when_enabled(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[FakeResponse(code=500), FakeResponse(code=200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(failover_on_business_error=True),
    )
    assert result.success is True
    assert post.call_count == 2


def test_http_status_and_elapsed_populated(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(code=200),
    )
    result = post_to_admins(
        ["http://a:8080"], "/api/registry", {}, "", (3, 5),
        policy=AdminCallPolicy(),
    )
    assert result.http_status == 200
    assert result.elapsed_ms is not None and result.elapsed_ms >= 0
    assert result.attempt_count == 1


def test_token_never_in_result(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.ConnectionError("boom"),
    )
    result = post_to_admins(
        ["http://a:8080"], "/api/registry", {}, "secret-token", (3, 5),
        policy=AdminCallPolicy(),
    )
    assert "secret-token" not in (result.error or "")


def test_policy_from_config_clamps_caps():
    config = XXLJobConfig.from_mapping(
        {
            "XXL_JOB_ADMIN_ADDRESSES": ["http://a:8080"],
            "XXL_JOB_EXECUTOR_APP_NAME": "app",
            "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
            "XXL_JOB_ADMIN_RETRY_COUNT": 999,
            "XXL_JOB_ADMIN_RETRY_BACKOFF": 999.0,
        }
    )
    policy = AdminCallPolicy.from_config(config)
    assert policy.retry_count == RETRY_COUNT_CAP
    assert policy.retry_backoff == RETRY_BACKOFF_CAP

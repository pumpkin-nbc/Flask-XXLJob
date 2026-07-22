"""Admin call-result error classification tests (0.1.2)."""

from __future__ import annotations

import requests

from flask_xxljob.client import (
    ERROR_BUSINESS,
    ERROR_CONFIG,
    ERROR_HTTP,
    ERROR_INVALID_JSON,
    ERROR_NETWORK,
    ERROR_TIMEOUT,
    post_to_admins,
)


class FakeResponse:
    def __init__(self, code=200, status_code=200, bad_json=False):
        self.status_code = status_code
        self._code = code
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("no json")
        return {"code": self._code, "msg": "m", "content": None}


def call(**kwargs):
    return post_to_admins(
        ["http://a:8080"], "/api/registry", {}, "", (3, 5), **kwargs
    )


def test_success_has_no_error_type(mocker):
    mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse(200))
    result = call()
    assert result.success is True
    assert result.error_type is None


def test_no_admin_configured_is_config():
    result = post_to_admins([], "/api/registry", {}, "", (3, 5))
    assert result.success is False
    assert result.error_type == ERROR_CONFIG


def test_timeout_is_timeout(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.Timeout("slow"),
    )
    assert call().error_type == ERROR_TIMEOUT


def test_connection_error_is_network(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.ConnectionError("down"),
    )
    assert call().error_type == ERROR_NETWORK


def test_non_200_is_http(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(status_code=502),
    )
    assert call().error_type == ERROR_HTTP


def test_invalid_json_is_invalid_json(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(bad_json=True),
    )
    assert call().error_type == ERROR_INVALID_JSON


def test_business_failure_is_business(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(code=500),
    )
    result = call()
    assert result.success is False
    assert result.error_type == ERROR_BUSINESS


def test_error_result_never_contains_token(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=requests.ConnectionError("down"),
    )
    result = post_to_admins(["http://a:8080"], "/api/registry", {}, "secret-token", (3, 5))
    assert "secret-token" not in (result.error or "")

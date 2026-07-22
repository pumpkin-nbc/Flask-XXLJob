"""CallResult / AdminCallResult tests (0.1.1)."""

from __future__ import annotations

import requests

from flask_xxljob import AdminCallResult, CallResult
from flask_xxljob.client import post_to_admins


def test_admin_call_result_is_call_result_alias():
    assert AdminCallResult is CallResult


def test_message_prefers_msg_then_error():
    r1 = CallResult(success=True, msg="ok")
    assert r1.message == "ok"
    r2 = CallResult(success=False, error="boom")
    assert r2.message == "boom"


def test_admin_address_aliases_address():
    r = CallResult(success=True, address="http://a:8080")
    assert r.admin_address == "http://a:8080"


class FakeResponse:
    def __init__(self, code, status_code=200):
        self.status_code = status_code
        self._code = code

    def json(self):
        return {"code": self._code, "msg": "m", "content": None}


def test_registration_failover_on_business_failure(mocker):
    # 注册：业务失败会继续尝试下一个地址。
    # Registration: a business failure moves on to the next address.
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[FakeResponse(500), FakeResponse(200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"], "/api/registry", {}, "", (3, 5)
    )
    assert result.success is True
    assert post.call_count == 2


def test_callback_stops_on_business_response(mocker):
    # 回调：收到有效业务响应即停止，不向第二个地址重复发送。
    # Callback: stop on a valid business response, no duplicate send.
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[FakeResponse(500), FakeResponse(200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"],
        "/api/callback",
        [],
        "",
        (3, 5),
        stop_on_business_response=True,
    )
    assert result.success is False
    assert post.call_count == 1


def test_callback_failover_on_network_error(mocker):
    # 回调：网络错误时才切换到下一个地址。
    # Callback: only a network error triggers failover.
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[requests.ConnectionError("down"), FakeResponse(200)],
    )
    result = post_to_admins(
        ["http://a:8080", "http://b:8080"],
        "/api/callback",
        [],
        "",
        (3, 5),
        stop_on_business_response=True,
    )
    assert result.success is True
    assert post.call_count == 2

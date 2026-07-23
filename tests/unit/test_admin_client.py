"""Admin registry client tests."""

from __future__ import annotations

import requests

from flask_xxljob.client import ACCESS_TOKEN_HEADER
from flask_xxljob.client.admin_client import (
    REGISTRY_PATH,
    REGISTRY_REMOVE_PATH,
    AdminClient,
)
from flask_xxljob.config import XXLJobConfig
from flask_xxljob.model.registry import RegistryRequest


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
        return {"code": self._code, "msg": "err" if self._code != 200 else None}


def test_registry_calls_official_path(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = AdminClient(make_config())
    req = RegistryRequest.for_executor("app", "http://127.0.0.1:5001")
    result = client.registry(req)
    assert result.success is True
    assert post.call_args.args[0].endswith(REGISTRY_PATH)
    assert post.call_args.kwargs["json"] == req.to_wire()


def test_registry_remove_calls_official_path(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = AdminClient(make_config())
    client.registry_remove(RegistryRequest.for_executor("app", "http://127.0.0.1:5001"))
    assert post.call_args.args[0].endswith(REGISTRY_REMOVE_PATH)


def test_registry_token_header(mocker):
    post = mocker.patch("flask_xxljob.client.requests.post", return_value=FakeResponse())
    client = AdminClient(make_config(XXL_JOB_ACCESS_TOKEN="tok"))
    client.registry(RegistryRequest.for_executor("app", "addr"))
    assert post.call_args.kwargs["headers"][ACCESS_TOKEN_HEADER] == "tok"


def test_registry_failover(mocker):
    post = mocker.patch(
        "flask_xxljob.client.requests.post",
        side_effect=[requests.ConnectionError("x"), FakeResponse()],
    )
    client = AdminClient(make_config())
    result = client.registry(RegistryRequest.for_executor("app", "addr"))
    assert result.success is True
    assert result.address == "http://b:8080"
    assert post.call_count == 2


def test_registry_business_failure(mocker):
    mocker.patch(
        "flask_xxljob.client.requests.post",
        return_value=FakeResponse(code=500),
    )
    client = AdminClient(make_config(XXL_JOB_ADMIN_ADDRESSES=["http://a:8080"]))
    result = client.registry(RegistryRequest.for_executor("app", "addr"))
    assert result.success is False
    assert result.code == 500

"""Complete bilingual integration example tests."""

from __future__ import annotations

import pytest

from examples.complete_integration import app as example
from flask_xxljob import CallResult


@pytest.fixture
def complete_app():
    return example.create_app(
        {
            "TESTING": True,
            "XXL_JOB_AUTO_REGISTER": False,
            "XXL_JOB_ACCESS_TOKEN": "admin-token",
            "INTERNAL_RESULT_TOKEN": "internal-token",
        }
    )


def _headers():
    return {"XXL-JOB-ACCESS-TOKEN": "admin-token"}


def test_complete_example_protocol_endpoints(complete_app):
    client = complete_app.test_client()
    assert client.get("/healthz").get_json() == {"status": "ok"}
    assert client.post("/xxl-job/beat", headers=_headers(), json={}).get_json()["code"] == 200

    trigger = client.post(
        "/xxl-job/run",
        headers=_headers(),
        json={
            "jobId": 1,
            "executorHandler": "demoJobHandler",
            "executorParams": '{"customerId": 42}',
            "logId": 10001,
            "logDateTime": 1784736000000,
        },
    ).get_json()
    assert trigger == {"code": 200, "msg": None, "content": "accepted"}

    idle = client.post(
        "/xxl-job/idleBeat", headers=_headers(), json={"jobId": 1}
    ).get_json()
    assert idle["code"] == 200
    killed = client.post(
        "/xxl-job/kill", headers=_headers(), json={"jobId": 1}
    ).get_json()
    assert killed["code"] == 200
    log = client.post(
        "/xxl-job/log",
        headers=_headers(),
        json={"logDateTim": 1784736000000, "logId": 10001, "fromLineNum": 1},
    ).get_json()
    assert log["code"] == 200
    assert "demo log" in log["content"]["logContent"]


def test_complete_example_result_endpoint_reports_success(complete_app, mocker):
    callback = mocker.patch.object(
        example.xxl_job,
        "callback_success",
        return_value=CallResult(success=True, address="http://admin"),
    )

    response = complete_app.test_client().post(
        "/internal/task-result",
        headers={"X-Internal-Token": "internal-token"},
        json={
            "logId": 10001,
            "logDateTime": 1784736000000,
            "success": True,
            "message": "completed",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    callback.assert_called_once_with(
        app=complete_app,
        log_id=10001,
        log_date_time=1784736000000,
        message="completed",
    )


@pytest.mark.parametrize(
    "headers,payload,status",
    [
        ({}, {}, 401),
        (
            {"X-Internal-Token": "internal-token"},
            {"logId": True, "logDateTime": 1, "success": True},
            400,
        ),
        (
            {"X-Internal-Token": "internal-token"},
            {"logId": 1, "logDateTime": 1, "success": "yes"},
            400,
        ),
    ],
)
def test_complete_example_result_endpoint_rejects_invalid_input(
    complete_app, headers, payload, status
):
    response = complete_app.test_client().post(
        "/internal/task-result", headers=headers, json=payload
    )
    assert response.status_code == status

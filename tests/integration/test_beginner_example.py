"""Beginner example smoke tests."""

from __future__ import annotations

from examples.beginner.app import app


def test_beginner_example_is_runnable():
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.post("/xxl-job/beat", json={}).get_json()["code"] == 200

    response = client.post(
        "/xxl-job/run",
        json={
            "jobId": 1,
            "executorHandler": "demoJobHandler",
            "executorParams": '{"name": "beginner"}',
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "code": 200,
        "msg": None,
        "content": "任务已收到 / job received",
    }

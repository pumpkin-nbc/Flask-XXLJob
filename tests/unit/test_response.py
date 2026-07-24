"""Response model tests."""

from __future__ import annotations

from flask_xxljob import LogResponse, XXLJobResponse


def test_success_response():
    resp = XXLJobResponse.success()
    assert resp.code == 200
    assert resp.msg is None
    assert resp.content is None
    assert resp.is_success is True
    assert resp.to_dict() == {"code": 200, "msg": None, "content": None}


def test_success_response_with_msg():
    resp = XXLJobResponse.success(content="accepted", msg="job queued")
    assert resp.code == 200
    assert resp.msg == "job queued"
    assert resp.content == "accepted"
    assert resp.is_success is True
    assert resp.to_dict() == {
        "code": 200,
        "msg": "job queued",
        "content": "accepted",
    }


def test_failure_response():
    resp = XXLJobResponse.failure("boom")
    assert resp.code == 500
    assert resp.msg == "boom"
    assert resp.is_success is False


def test_log_response_to_wire():
    resp = LogResponse(from_line_num=1, to_line_num=9, log_content="text", is_end=True)
    assert resp.to_wire() == {
        "fromLineNum": 1,
        "toLineNum": 9,
        "logContent": "text",
        "isEnd": True,
    }

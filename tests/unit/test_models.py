"""Protocol model tests."""

from __future__ import annotations

from flask_xxljob import (
    CallbackRequest,
    IdleBeatRequest,
    KillRequest,
    LogRequest,
    RegistryRequest,
    TriggerRequest,
)


def test_trigger_from_wire_maps_official_fields():
    data = {
        "jobId": 7,
        "executorHandler": "demoHandler",
        "executorParams": '{"a": 1}',
        "executorBlockStrategy": "SERIAL_EXECUTION",
        "executorTimeout": 60,
        "logId": 100,
        "logDateTime": 1234567890,
        "glueType": "BEAN",
        "glueSource": "",
        "glueUpdatetime": 42,
        "broadcastIndex": 0,
        "broadcastTotal": 1,
    }
    req = TriggerRequest.from_wire(data)
    assert req.job_id == 7
    assert req.executor_handler == "demoHandler"
    assert req.glue_update_time == 42
    assert req.to_wire()["glueUpdatetime"] == 42


def test_trigger_parse_params_json():
    req = TriggerRequest(executor_params='{"a": 1}')
    assert req.parse_params() == {"a": 1}
    # original preserved
    assert req.executor_params == '{"a": 1}'


def test_trigger_parse_params_blank_returns_none():
    assert TriggerRequest(executor_params="   ").parse_params() is None
    assert TriggerRequest(executor_params="").parse_params() is None


def test_trigger_parse_params_non_json_returns_raw():
    assert TriggerRequest(executor_params="hello").parse_params() == "hello"


def test_idle_beat_and_kill_models():
    assert IdleBeatRequest.from_wire({"jobId": 3}).job_id == 3
    assert KillRequest.from_wire({"jobId": 4}).job_id == 4


def test_log_request_uses_official_typo_field():
    req = LogRequest.from_wire({"logDateTim": 111, "logId": 222, "fromLineNum": 5})
    assert req.log_date_time == 111
    assert req.log_id == 222
    assert req.from_line_num == 5
    assert req.to_wire()["logDateTim"] == 111


def test_callback_request_uses_official_typo_field():
    req = CallbackRequest(log_id=1, log_date_time=2, handle_code=200, handle_msg="ok")
    wire = req.to_wire()
    assert wire == {
        "logId": 1,
        "logDateTim": 2,
        "handleCode": 200,
        "handleMsg": "ok",
    }


def test_registry_request_for_executor():
    req = RegistryRequest.for_executor("app", "http://127.0.0.1:5001")
    assert req.to_wire() == {
        "registryGroup": "EXECUTOR",
        "registryKey": "app",
        "registryValue": "http://127.0.0.1:5001",
    }

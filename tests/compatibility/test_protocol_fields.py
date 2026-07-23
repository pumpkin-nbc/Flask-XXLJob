"""Compatibility tests: strict field mapping against XXL-JOB 2.4.1.

These tests pin the exact official wire field names, including the known
official typos ``logDateTim`` and ``glueUpdatetime``.
"""

from __future__ import annotations

from flask_xxljob.model.callback import CallbackRequest
from flask_xxljob.model.idle_beat import IdleBeatRequest
from flask_xxljob.model.kill import KillRequest
from flask_xxljob.model.log import LogRequest
from flask_xxljob.model.registry import RegistryRequest
from flask_xxljob.model.trigger import TriggerRequest
from flask_xxljob.response.executor import FAIL_CODE, SUCCESS_CODE
from flask_xxljob.response.log import LogResponse


def test_trigger_param_field_names():
    keys = set(TriggerRequest().to_wire().keys())
    assert keys == {
        "jobId",
        "executorHandler",
        "executorParams",
        "executorBlockStrategy",
        "executorTimeout",
        "logId",
        "logDateTime",
        "glueType",
        "glueSource",
        "glueUpdatetime",
        "broadcastIndex",
        "broadcastTotal",
    }


def test_idle_beat_and_kill_field_names():
    assert set(IdleBeatRequest().to_wire()) == {"jobId"}
    assert set(KillRequest().to_wire()) == {"jobId"}


def test_log_param_field_names():
    assert set(LogRequest().to_wire()) == {"logDateTim", "logId", "fromLineNum"}


def test_log_result_field_names():
    assert set(LogResponse().to_wire()) == {
        "fromLineNum",
        "toLineNum",
        "logContent",
        "isEnd",
    }


def test_handle_callback_param_field_names():
    assert set(CallbackRequest().to_wire()) == {
        "logId",
        "logDateTim",
        "handleCode",
        "handleMsg",
    }


def test_registry_param_field_names_and_group():
    wire = RegistryRequest.for_executor("app", "addr").to_wire()
    assert set(wire) == {"registryGroup", "registryKey", "registryValue"}
    assert wire["registryGroup"] == "EXECUTOR"


def test_official_status_codes():
    assert SUCCESS_CODE == 200
    assert FAIL_CODE == 500

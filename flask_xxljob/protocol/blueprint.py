"""
XXL-JOB 执行器接口 Blueprint。

XXL-JOB executor endpoint blueprint.

提供官方五个执行器接口：``/beat``、``/idleBeat``、``/run``、``/kill``、``/log``。
``/beat`` 由插件直接处理，其余接口调用 Flask 项目注册的请求处理函数。

Provides the five official executor endpoints: ``/beat``, ``/idleBeat``,
``/run``, ``/kill`` and ``/log``. ``/beat`` is handled directly by the plugin;
the others dispatch to request-callbacks registered by the Flask project.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request

from ..model.idle_beat import IdleBeatRequest
from ..model.kill import KillRequest
from ..model.log import LogRequest
from ..model.trigger import TriggerRequest
from ..response.executor import XXLJobResponse
from ..response.log import LogResponse
from .parser import RequestParseError, parse_and_validate, parse_json_body
from .validator import check_access_token, extract_request_token

logger = logging.getLogger("flask_xxljob.protocol")

# 未注册处理函数时的官方错误信息 / Errors when a callback is not configured.
RUN_NOT_CONFIGURED = "XXL-JOB run callback is not configured"
IDLE_BEAT_NOT_CONFIGURED = "XXL-JOB idleBeat callback is not configured"
KILL_NOT_CONFIGURED = "XXL-JOB kill callback is not configured"
LOG_NOT_CONFIGURED = "XXL-JOB log callback is not configured"


def _runtime() -> Any:
    return current_app.extensions["xxljob"]


def _json(response: XXLJobResponse) -> Response:
    return jsonify(response.to_dict())


def _coerce_response(result: Any) -> XXLJobResponse:
    """
    将处理函数返回值转换成标准响应。

    Convert a callback return value into a standard response.
    """
    if isinstance(result, XXLJobResponse):
        return result
    if result is None or result is True:
        return XXLJobResponse.success()
    if result is False:
        return XXLJobResponse.failure("callback reported failure")
    return XXLJobResponse.success()


def _token_ok(runtime: Any) -> bool:
    return check_access_token(
        runtime.config.access_token, extract_request_token(request.headers)
    )


def build_blueprint(name: str, url_prefix: str) -> Blueprint:
    """
    构造 XXL-JOB 执行器 Blueprint。

    每个 Flask 应用使用独立的 Blueprint 实例，避免重复注册冲突。

    Build the XXL-JOB executor blueprint.

    Each Flask application uses an independent blueprint instance to avoid
    duplicate-registration conflicts.
    """
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix or None)

    @blueprint.post("/beat")
    def beat() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure("The access token is wrong."))
        # /beat 不调用业务系统，Runtime 正常即返回成功。
        # /beat does not touch the business system; success when runtime is ok.
        return _json(XXLJobResponse.success())

    @blueprint.post("/run")
    def run() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure("The access token is wrong."))

        callback = runtime.callback_registry.run
        if callback is None:
            return _json(XXLJobResponse.failure(RUN_NOT_CONFIGURED))

        try:
            data, error = parse_and_validate(
                request.get_data(),
                runtime.config.max_request_size,
                runtime.config.max_param_length,
            )
        except RequestParseError as exc:
            return _json(XXLJobResponse.failure(str(exc)))
        if error:
            return _json(XXLJobResponse.failure(error))

        trigger = TriggerRequest.from_wire(data if isinstance(data, dict) else {})
        return _dispatch(callback, trigger)

    @blueprint.post("/idleBeat")
    def idle_beat() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure("The access token is wrong."))

        callback = runtime.callback_registry.idle_beat
        if callback is None:
            return _json(XXLJobResponse.failure(IDLE_BEAT_NOT_CONFIGURED))

        try:
            data = parse_json_body(request.get_data(), runtime.config.max_request_size)
        except RequestParseError as exc:
            return _json(XXLJobResponse.failure(str(exc)))

        model = IdleBeatRequest.from_wire(data if isinstance(data, dict) else {})
        return _dispatch(callback, model)

    @blueprint.post("/kill")
    def kill() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure("The access token is wrong."))

        callback = runtime.callback_registry.kill
        if callback is None:
            return _json(XXLJobResponse.failure(KILL_NOT_CONFIGURED))

        try:
            data = parse_json_body(request.get_data(), runtime.config.max_request_size)
        except RequestParseError as exc:
            return _json(XXLJobResponse.failure(str(exc)))

        model = KillRequest.from_wire(data if isinstance(data, dict) else {})
        return _dispatch(callback, model)

    @blueprint.post("/log")
    def log() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure("The access token is wrong."))

        callback = runtime.callback_registry.log
        if callback is None:
            return _json(XXLJobResponse.failure(LOG_NOT_CONFIGURED))

        try:
            data = parse_json_body(request.get_data(), runtime.config.max_request_size)
        except RequestParseError as exc:
            return _json(XXLJobResponse.failure(str(exc)))

        model = LogRequest.from_wire(data if isinstance(data, dict) else {})
        try:
            result = callback(model)
        except Exception as exc:  # noqa: BLE001 - 隔离用户处理函数 / isolate user callback
            logger.exception("XXL-JOB /log callback raised an exception.")
            return _json(XXLJobResponse.failure(f"log callback error: {type(exc).__name__}"))

        if isinstance(result, XXLJobResponse):
            return _json(result)
        if isinstance(result, LogResponse):
            return _json(XXLJobResponse.success(content=result.to_wire()))
        return _json(XXLJobResponse.failure("log callback must return a LogResponse"))

    def _dispatch(callback: Callable[[Any], Any], model: Any) -> Response:
        try:
            result = callback(model)
        except Exception as exc:  # noqa: BLE001 - 隔离用户处理函数 / isolate user callback
            logger.exception("XXL-JOB executor callback raised an exception.")
            return _json(XXLJobResponse.failure(f"callback error: {type(exc).__name__}"))
        return _json(_coerce_response(result))

    return blueprint

"""
XXL-JOB 执行器接口 Blueprint。

XXL-JOB executor endpoint blueprint.

提供官方五个执行器接口：``/beat``、``/idleBeat``、``/run``、``/kill``、``/log``。
``/beat`` 由插件直接处理，其余接口调用 Flask 项目注册的请求处理函数。所有错误都
返回 XXL-JOB 标准 JSON，不会返回 Flask/Werkzeug HTML 错误页。

Provides the five official executor endpoints: ``/beat``, ``/idleBeat``,
``/run``, ``/kill`` and ``/log``. ``/beat`` is handled directly by the plugin;
the others dispatch to request-callbacks registered by the Flask project. Every
error returns XXL-JOB standard JSON and never a Flask/Werkzeug HTML error page.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from ..model.coerce import ModelParseError
from ..model.idle_beat import IdleBeatRequest
from ..model.kill import KillRequest
from ..model.log import LogRequest
from ..model.trigger import TriggerRequest
from ..response.executor import XXLJobResponse
from ..response.log import LogResponse
from .parser import RequestParseError, check_param_length, parse_json_object
from .validator import ACCESS_TOKEN_ERROR, check_access_token, extract_request_token

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


def _coerce_response(result: Any, endpoint: str) -> XXLJobResponse:
    """
    将处理函数返回值转换成标准响应。

    只接受 :class:`XXLJobResponse`；其他返回类型（``None``、``dict``、``str``、
    ``bool`` 等）返回明确的 "unsupported response type" 失败，绝不产生内部异常。

    Convert a callback return value into a standard response.

    Only :class:`XXLJobResponse` is accepted; any other return type (``None``,
    ``dict``, ``str``, ``bool`` and so on) yields an explicit "unsupported
    response type" failure and never raises an internal exception.
    """
    if isinstance(result, XXLJobResponse):
        return result
    return XXLJobResponse.failure(
        f"XXL-JOB {endpoint} callback returned an unsupported response type"
    )


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
            return _json(XXLJobResponse.failure(ACCESS_TOKEN_ERROR))
        # /beat 不调用业务系统，Runtime 正常即返回成功。
        # /beat does not touch the business system; success when runtime is ok.
        return _json(XXLJobResponse.success())

    @blueprint.post("/run")
    def run() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure(ACCESS_TOKEN_ERROR))

        callback = runtime.callback_registry.run
        if callback is None:
            return _json(XXLJobResponse.failure(RUN_NOT_CONFIGURED))

        data = _parse_body(runtime)
        if isinstance(data, Response):
            return data
        error = check_param_length(data, runtime.config.max_param_length)
        if error:
            return _json(XXLJobResponse.failure(error))

        model = _build_model(TriggerRequest, data)
        if isinstance(model, Response):
            return model
        return _dispatch(callback, model, "run")

    @blueprint.post("/idleBeat")
    def idle_beat() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure(ACCESS_TOKEN_ERROR))

        callback = runtime.callback_registry.idle_beat
        if callback is None:
            return _json(XXLJobResponse.failure(IDLE_BEAT_NOT_CONFIGURED))

        data = _parse_body(runtime)
        if isinstance(data, Response):
            return data
        model = _build_model(IdleBeatRequest, data)
        if isinstance(model, Response):
            return model
        return _dispatch(callback, model, "idleBeat")

    @blueprint.post("/kill")
    def kill() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure(ACCESS_TOKEN_ERROR))

        callback = runtime.callback_registry.kill
        if callback is None:
            return _json(XXLJobResponse.failure(KILL_NOT_CONFIGURED))

        data = _parse_body(runtime)
        if isinstance(data, Response):
            return data
        model = _build_model(KillRequest, data)
        if isinstance(model, Response):
            return model
        return _dispatch(callback, model, "kill")

    @blueprint.post("/log")
    def log() -> Response:
        runtime = _runtime()
        if not _token_ok(runtime):
            return _json(XXLJobResponse.failure(ACCESS_TOKEN_ERROR))

        callback = runtime.callback_registry.log
        if callback is None:
            return _json(XXLJobResponse.failure(LOG_NOT_CONFIGURED))

        data = _parse_body(runtime)
        if isinstance(data, Response):
            return data
        model = _build_model(LogRequest, data)
        if isinstance(model, Response):
            return model

        try:
            result = callback(model)
        except Exception:  # noqa: BLE001 - 隔离用户处理函数 / isolate user callback
            # traceback 仅写入本地日志，不返回给 XXL-JOB。
            # The traceback is logged locally only and never returned to XXL-JOB.
            logger.exception("XXL-JOB /log callback raised an exception (logId=%s).", model.log_id)
            return _json(XXLJobResponse.failure("XXL-JOB log callback execution failed"))

        if isinstance(result, XXLJobResponse):
            return _json(result)
        if isinstance(result, LogResponse):
            return _json(XXLJobResponse.success(content=result.to_wire()))
        return _json(
            XXLJobResponse.failure(
                "XXL-JOB log callback returned an unsupported response type"
            )
        )

    @blueprint.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException) -> Response:
        # 执行器接口的 HTTP 错误（例如 405/404）统一返回 XXL-JOB JSON。
        # HTTP errors on executor endpoints (e.g. 405/404) return XXL-JOB JSON.
        return _json(XXLJobResponse.failure(f"XXL-JOB request error: {exc.name}"))

    @blueprint.errorhandler(Exception)
    def _handle_unexpected(exc: Exception) -> Response:
        logger.exception("Unexpected error in XXL-JOB executor endpoint.")
        return _json(XXLJobResponse.failure("XXL-JOB internal protocol error"))

    def _parse_body(runtime: Any) -> Any:
        try:
            return parse_json_object(request.get_data(), runtime.config.max_request_size)
        except RequestParseError as exc:
            return _json(XXLJobResponse.failure(str(exc)))

    def _build_model(model_cls: Any, data: dict) -> Any:
        try:
            return model_cls.from_wire(data)
        except ModelParseError as exc:
            return _json(XXLJobResponse.failure(f"invalid request field: {exc}"))

    def _dispatch(callback: Callable[[Any], Any], model: Any, endpoint: str) -> Response:
        try:
            result = callback(model)
        except Exception:  # noqa: BLE001 - 隔离用户处理函数 / isolate user callback
            # traceback 仅写入本地日志，不返回给 XXL-JOB。
            # The traceback is logged locally only and never returned to XXL-JOB.
            logger.exception("XXL-JOB /%s callback raised an exception.", endpoint)
            return _json(
                XXLJobResponse.failure(f"XXL-JOB {endpoint} callback execution failed")
            )
        return _json(_coerce_response(result, endpoint))

    return blueprint


__all__ = ["build_blueprint"]

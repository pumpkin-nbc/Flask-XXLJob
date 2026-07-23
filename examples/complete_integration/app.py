"""完整的 Flask-XXLJob 接入示例。 / Complete Flask-XXLJob integration example."""

from __future__ import annotations

import hmac
import os
from typing import Any, Mapping, Optional

from flask import Flask, current_app, jsonify
from flask import request as flask_request

from flask_xxljob import (
    FlaskXXLJob,
    LogResponse,
    TriggerRequest,
    XXLJobResponse,
)

xxl_job = FlaskXXLJob()


class TaskGateway:
    """替换为你的 Celery、消息队列或任务服务客户端。 / Replace with your task client."""

    def submit(self, trigger: TriggerRequest) -> None:
        # 必须把 logId/logDateTime 一并交给任务服务，完成后回传这两个值。
        # Pass logId/logDateTime to the task service for the final callback.
        current_app.logger.info(
            "submit handler=%s job_id=%s log_id=%s params=%r",
            trigger.executor_handler,
            trigger.job_id,
            trigger.log_id,
            trigger.parse_params(),
        )

    def is_idle(self, job_id: int) -> bool:
        # 生产环境应查询真实任务服务。 / Query the real task service in production.
        current_app.logger.info("idle check job_id=%s", job_id)
        return True

    def cancel(self, job_id: int) -> bool:
        # 生产环境应向真实任务服务发送取消请求。
        # Send cancellation to the real task service in production.
        current_app.logger.info("cancel job_id=%s", job_id)
        return True

    def read_log(self, log_id: int, from_line_num: int) -> tuple:
        # 生产环境应从日志服务分页读取。 / Read a page from your log service.
        line = f"demo log for logId={log_id}"
        return ([line] if from_line_num <= 1 else []), True


def _gateway() -> TaskGateway:
    return current_app.extensions["complete_example_task_gateway"]


def _submit_task(trigger: TriggerRequest, content: str) -> XXLJobResponse:
    """接收调度请求并提交任务，切勿在此执行耗时任务。 / Submit, do not execute here."""
    try:
        _gateway().submit(trigger)
    except Exception:  # noqa: BLE001 - the example isolates the business adapter
        current_app.logger.exception("Failed to submit XXL-JOB task")
        return XXLJobResponse.failure("task submission failed")
    return XXLJobResponse.success(content=content)


@xxl_job.on_run("demoJobHandler")
def handle_demo(trigger: TriggerRequest) -> XXLJobResponse:
    """自动接收 ``demoJobHandler``。 / Automatically handle this JobHandler."""
    return _submit_task(trigger, "accepted")


@xxl_job.on_run("reportJobHandler")
def handle_report(trigger: TriggerRequest) -> XXLJobResponse:
    """自动接收 ``reportJobHandler``。 / Automatically handle this JobHandler."""
    return _submit_task(trigger, "report accepted")


@xxl_job.on_idle_beat
def handle_idle_beat(request: Any) -> XXLJobResponse:
    if _gateway().is_idle(request.job_id):
        return XXLJobResponse.success()
    return XXLJobResponse.failure("job is running")


@xxl_job.on_kill
def handle_kill(request: Any) -> XXLJobResponse:
    if _gateway().cancel(request.job_id):
        return XXLJobResponse.success()
    return XXLJobResponse.failure("task could not be cancelled")


@xxl_job.on_log
def handle_log(request: Any) -> LogResponse:
    lines, is_end = _gateway().read_log(request.log_id, request.from_line_num)
    return LogResponse(
        from_line_num=request.from_line_num,
        to_line_num=request.from_line_num + len(lines),
        log_content="\n".join(lines),
        is_end=is_end,
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _admin_addresses() -> list:
    raw = os.environ.get(
        "XXL_JOB_ADMIN_ADDRESSES", "http://127.0.0.1:8080/xxl-job-admin"
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


def _valid_result_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, Mapping):
        return "request body must be a JSON object"
    for field in ("logId", "logDateTime"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{field} must be an integer"
    if not isinstance(payload.get("success"), bool):
        return "success must be a boolean"
    message = payload.get("message", "")
    if not isinstance(message, str):
        return "message must be a string"
    return None


def _register_host_routes(app: Flask) -> None:
    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify(status="ok")

    @app.route("/internal/task-result", methods=["POST"])
    def task_result():
        # 此接口供业务任务服务调用，不是 XXL-JOB 官方接口。
        # This endpoint is called by your task service, not by XXL-JOB admin.
        configured_token = app.config["INTERNAL_RESULT_TOKEN"]
        request_token = flask_request.headers.get("X-Internal-Token", "")
        if not configured_token:
            return jsonify(error="INTERNAL_RESULT_TOKEN is not configured"), 503
        if not hmac.compare_digest(configured_token, request_token):
            return jsonify(error="unauthorized"), 401

        payload = flask_request.get_json(silent=True)
        error = _valid_result_payload(payload)
        if error:
            return jsonify(error=error), 400

        flask_app = current_app._get_current_object()
        callback = xxl_job.callback_success if payload["success"] else xxl_job.callback_failure
        result = callback(
            app=flask_app,
            log_id=payload["logId"],
            log_date_time=payload["logDateTime"],
            message=payload.get("message", ""),
        )
        response = {
            "success": result.success,
            "adminAddress": result.admin_address,
            "errorType": result.error_type,
            "message": result.message,
        }
        return jsonify(response), 200 if result.success else 502


def create_app(config: Optional[Mapping[str, Any]] = None) -> Flask:
    """创建可供 Flask CLI 或 WSGI Server 加载的应用。 / Build the Flask app."""
    app = Flask(__name__)
    route_prefix = os.environ.get("XXL_JOB_ROUTE_PREFIX", "/xxl-job")
    app.config.from_mapping(
        XXL_JOB_ADMIN_ADDRESSES=_admin_addresses(),
        XXL_JOB_ACCESS_TOKEN=os.environ.get("XXL_JOB_ACCESS_TOKEN", ""),
        XXL_JOB_EXECUTOR_APP_NAME=os.environ.get(
            "XXL_JOB_EXECUTOR_APP_NAME", "complete-flask-executor"
        ),
        XXL_JOB_EXECUTOR_ADDRESS=os.environ.get(
            "XXL_JOB_EXECUTOR_ADDRESS", "http://127.0.0.1:5001/xxl-job"
        ),
        XXL_JOB_ROUTE_PREFIX=route_prefix,
        XXL_JOB_AUTO_REGISTER=_env_bool("XXL_JOB_AUTO_REGISTER", False),
        INTERNAL_RESULT_TOKEN=os.environ.get("INTERNAL_RESULT_TOKEN", ""),
    )
    if config:
        app.config.update(config)

    app.extensions["complete_example_task_gateway"] = TaskGateway()
    _register_host_routes(app)
    xxl_job.init_app(app)
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001)

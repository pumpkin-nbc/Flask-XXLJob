"""
Flask-XXLJob 多应用示例。

Flask-XXLJob multiple-applications example.

演示一个共享的 ``FlaskXXLJob`` 实例如何在多个 Flask 应用上使用应用级注册 API 注册
各自独立的处理函数，实现应用间隔离。

Demonstrates how a single shared ``FlaskXXLJob`` instance registers independent
handlers per Flask application using the application-level registration API,
providing per-application isolation.

运行 / Run::

    .venv\\Scripts\\python.exe examples\\multiple_apps\\app.py

注意：示例中不包含任何真实 Token 或内网地址。
Note: this example contains no real token or internal address.
"""

from __future__ import annotations

import os

from flask import Flask

from flask_xxljob import FlaskXXLJob, XXLJobResponse

xxl_job = FlaskXXLJob()


def _config(app_name: str, port: int) -> dict:
    return dict(
        XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
        XXL_JOB_ACCESS_TOKEN=os.environ.get("XXL_JOB_ACCESS_TOKEN", ""),
        XXL_JOB_EXECUTOR_APP_NAME=app_name,
        XXL_JOB_EXECUTOR_ADDRESS=f"http://127.0.0.1:{port}",
        XXL_JOB_AUTO_REGISTER=False,
    )


def create_reports_app() -> Flask:
    app = Flask("reports")
    app.config.update(_config("reports-executor", 5001))
    xxl_job.init_app(app)

    def handle_run(request):
        return XXLJobResponse.success(content="reports ran")

    xxl_job.set_run_callback(app, handle_run)
    return app


def create_billing_app() -> Flask:
    app = Flask("billing")
    app.config.update(_config("billing-executor", 5002))
    xxl_job.init_app(app)

    def handle_run(request):
        return XXLJobResponse.success(content="billing ran")

    xxl_job.set_run_callback(app, handle_run)
    return app


reports_app = create_reports_app()
billing_app = create_billing_app()


if __name__ == "__main__":
    # 每个应用拥有独立的处理函数与运行时。
    # Each application has its own handlers and runtime.
    r = reports_app.test_client().post("/run", json={"jobId": 1})
    b = billing_app.test_client().post("/run", json={"jobId": 1})
    print("reports:", r.json["content"])
    print("billing:", b.json["content"])

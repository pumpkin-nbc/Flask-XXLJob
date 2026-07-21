"""
Application Factory 示例包。

Application Factory example package.
"""

from __future__ import annotations

import os

from flask import Flask

from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse

# 模块级扩展实例，供整个应用共享。
# Module-level extension instance shared across the application.
xxl_job = FlaskXXLJob()


def create_app(config=None):
    """
    构造并初始化 Flask 应用。

    Build and initialize the Flask application.
    """
    app = Flask(__name__)
    app.config.from_mapping(
        XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
        XXL_JOB_ACCESS_TOKEN=os.environ.get("XXL_JOB_ACCESS_TOKEN", ""),
        XXL_JOB_EXECUTOR_APP_NAME="factory-executor",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
        XXL_JOB_AUTO_REGISTER=False,
    )
    if config:
        app.config.update(config)

    xxl_job.init_app(app)
    _register_callbacks()
    return app


def _register_callbacks():
    @xxl_job.on_run
    def handle_run(request):
        # 提交到你自己的任务服务，不要在此执行任务。
        # Submit to your own task service; do not execute the task here.
        return XXLJobResponse.success()

    @xxl_job.on_idle_beat
    def handle_idle_beat(request):
        return XXLJobResponse.success()

    @xxl_job.on_kill
    def handle_kill(request):
        return XXLJobResponse.success()

    @xxl_job.on_log
    def handle_log(request):
        return LogResponse(
            from_line_num=request.from_line_num,
            to_line_num=request.from_line_num,
            log_content="",
            is_end=True,
        )

"""
Flask-XXLJob 基础示例（直接初始化）。

Basic Flask-XXLJob example (direct initialization).

运行 / Run::

    .venv\\Scripts\\python.exe examples\\basic\\app.py

注意：示例中不包含任何真实 Token 或内网地址。
Note: this example contains no real token or internal address.
"""

from __future__ import annotations

import os

from flask import Flask

from flask_xxljob import FlaskXXLJob, LogResponse, XXLJobResponse

app = Flask(__name__)
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
    # Token 从环境变量读取，避免硬编码。
    # Read the token from an environment variable to avoid hard-coding.
    XXL_JOB_ACCESS_TOKEN=os.environ.get("XXL_JOB_ACCESS_TOKEN", ""),
    XXL_JOB_EXECUTOR_APP_NAME="basic-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_AUTO_REGISTER=False,
)

xxl_job = FlaskXXLJob(app)


@xxl_job.on_run
def handle_run(request):
    # 将任务提交给你自己的任务服务，这里仅作演示。
    # Submit the task to your own task service; this is only a demo.
    print(f"submit job {request.job_id} params={request.parse_params()}")
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

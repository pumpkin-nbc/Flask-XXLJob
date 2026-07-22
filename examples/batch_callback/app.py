"""
Flask-XXLJob 批量回调示例。

Flask-XXLJob batch-callback example.

演示如何用 ``callback_many`` 在一次请求中上报多个任务结果。此处不真正发送网络请求，
仅展示 API 用法。

Demonstrates reporting several task results in one request with
``callback_many``. It does not actually perform a network call here; it only
shows the API usage.

运行 / Run::

    .venv\\Scripts\\python.exe examples\\batch_callback\\app.py

注意：示例中不包含任何真实 Token 或内网地址。
Note: this example contains no real token or internal address.
"""

from __future__ import annotations

import os

from flask import Flask

from flask_xxljob import CallbackRequest, FlaskXXLJob, XXLJobResponse

app = Flask(__name__)
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
    XXL_JOB_ACCESS_TOKEN=os.environ.get("XXL_JOB_ACCESS_TOKEN", ""),
    XXL_JOB_EXECUTOR_APP_NAME="batch-callback-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_AUTO_REGISTER=False,
    # 单批最多 50 条；超过会被拒绝且不发送任何数据。
    # At most 50 items per batch; exceeding it is rejected without sending.
    XXL_JOB_CALLBACK_BATCH_MAX_SIZE=50,
)

xxl_job = FlaskXXLJob(app)


@xxl_job.on_run
def handle_run(request):
    return XXLJobResponse.success()


def report_batch():
    """在一次请求中上报多个任务结果。 / Report several results in one request."""
    results = [
        CallbackRequest(log_id=1, log_date_time=1710000000000, handle_code=200),
        CallbackRequest(
            log_id=2,
            log_date_time=1710000000000,
            handle_code=500,
            handle_msg="任务执行失败",
        ),
    ]
    with app.app_context():
        return xxl_job.callback_many(results)


if __name__ == "__main__":
    # 需要真实 Admin 时才会实际发送；这里仅演示调用方式。
    # This only sends against a real admin; here it just shows how to call.
    print("Prepared a batch of 2 callbacks. Call report_batch() with a live admin.")

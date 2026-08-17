"""
Flask-XXLJob 注册状态示例。

Flask-XXLJob registry-status example.

演示如何用 ``get_status`` 查询插件运行状态，以及用 ``start_registry`` /
``stop_registry`` 控制 Registry 生命周期。状态只描述插件本身，绝不含 Token 或业务状态。

Demonstrates querying the plugin runtime status with ``get_status`` and
controlling the Registry lifecycle with ``start_registry`` /
``stop_registry``. The status describes only the plugin and never contains the
token or any business state.

运行 / Run::

    .venv\\Scripts\\python.exe examples\\registry_status\\app.py

    # CLI 状态 / CLI status
    flask --app examples.registry_status.app xxljob status

注意：示例中不包含任何真实 Token 或内网地址。
Note: this example contains no real token or internal address.
"""

from __future__ import annotations

import os

from flask import Flask

from flask_xxljob import FlaskXXLJob, XXLJobResponse

app = Flask(__name__)
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
    XXL_JOB_ACCESS_TOKEN=os.environ.get("XXL_JOB_ACCESS_TOKEN", ""),
    XXL_JOB_EXECUTOR_APP_NAME="registry-status-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_AUTO_REGISTER=False,
)

xxl_job = FlaskXXLJob(app)


@xxl_job.on_run("registryStatusJobHandler")
def handle_run(request):
    return XXLJobResponse.success()


if __name__ == "__main__":
    status = xxl_job.get_status(app)
    print("enabled:", status.enabled)
    print("auto_register:", status.auto_register)
    print("registered:", status.registered)
    print("registry_thread_running:", status.registry_thread_running)
    print("last_registry_time:", status.last_registry_time)

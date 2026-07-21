[English](getting-started.md) | [简体中文](getting-started.zh-CN.md)

# 快速开始

Flask-XXLJob 让 Flask 应用可以直接作为 XXL-JOB 2.4.1 执行器，不再经过 Java 中转服务。它只负责协议，实际任务由你的项目执行。

## 安装

```bash
pip install Flask-XXLJob
```

## 最小示例

```python
from flask import Flask
from flask_xxljob import FlaskXXLJob, XXLJobResponse

xxl_job = FlaskXXLJob()


def create_app():
    app = Flask(__name__)
    app.config.update(
        XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
        XXL_JOB_EXECUTOR_APP_NAME="project-executor",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )
    xxl_job.init_app(app)

    @xxl_job.on_run
    def handle_run(request):
        return XXLJobResponse.success()

    return app
```

## 后续流程

1. XXL-JOB Admin 通过 `POST /run` 触发你的执行器。
2. Flask-XXLJob 校验 Token、解析 `TriggerParam`，并调用你的 `on_run` 函数。
3. 你的函数把任务提交到自己的任务服务并返回响应。
4. 任务完成后，你的项目调用 `callback_success` 或 `callback_failure`。

详情参见 [request-callbacks.md](request-callbacks.md) 与 [callback.md](callback.md)。

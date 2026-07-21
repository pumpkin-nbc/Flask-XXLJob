[English](getting-started.md) | [简体中文](getting-started.zh-CN.md)

# Getting Started

Flask-XXLJob lets a Flask application act as an XXL-JOB 2.4.1 executor
directly, without a Java relay service. It handles the protocol only; your
project executes the actual tasks.

## Install

```bash
pip install Flask-XXLJob
```

## Minimal example

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

## What happens next

1. XXL-JOB admin triggers your executor via `POST /run`.
2. Flask-XXLJob validates the token, parses the `TriggerParam`, and calls your `on_run` function.
3. Your function submits the task to your own task service and returns a response.
4. When the task finishes, your project calls `callback_success` or `callback_failure`.

See [request-callbacks.md](request-callbacks.md) and [callback.md](callback.md) for details.

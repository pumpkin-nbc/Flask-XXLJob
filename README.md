[English](README.md) | [简体中文](README.zh-CN.md)

# Flask-XXLJob

A Flask extension that implements the official [XXL-JOB](https://github.com/xuxueli/xxl-job) 2.4.1 executor protocol, so a Flask project can act as an XXL-JOB executor directly without a Java relay service.

Flask-XXLJob is a **protocol adapter**. It handles protocol integration and does **not** execute business tasks.

## Features

- Implements the official XXL-JOB 2.4.1 executor endpoints: `/beat`, `/idleBeat`, `/run`, `/kill`, `/log`.
- Plain request callbacks (`on_run`, `on_idle_beat`, `on_kill`, `on_log`) instead of an executor adapter.
- Executor registration / deregistration with automatic renewal.
- Task-result callback client (`callback`, `callback_success`, `callback_failure`).
- Access token support using the official `XXL-JOB-ACCESS-TOKEN` header.
- Multiple admin addresses with failover.
- Flask Application Factory support and per-application runtime isolation.
- Minimal dependencies (`Flask`, `requests`), typed (`py.typed`).

## What it does not do

Flask-XXLJob never executes business tasks. It does not create thread pools, process pools, task queues, Celery tasks, or message queues; it does not manage task state, logs, timeouts, or cancellation; and it does not send the final task callback automatically. Your Flask project decides how to submit, execute, cancel, log, and finally call back.

## Installation

```bash
pip install Flask-XXLJob
```

## Quick start (Application Factory)

```python
from flask import Flask
from flask_xxljob import FlaskXXLJob, XXLJobResponse

xxl_job = FlaskXXLJob()


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
        XXL_JOB_ACCESS_TOKEN="",
        XXL_JOB_EXECUTOR_APP_NAME="project-executor",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )
    if config:
        app.config.update(config)

    xxl_job.init_app(app)

    @xxl_job.on_run
    def handle_run(request):
        # Submit the task to your own task service; do not execute it here.
        project_task_service.submit(
            handler=request.executor_handler,
            params=request.executor_params,
            job_id=request.job_id,
            log_id=request.log_id,
            log_date_time=request.log_date_time,
        )
        return XXLJobResponse.success()

    return app
```

## Task-result callback

When your task finishes, call back into XXL-JOB yourself:

```python
with app.app_context():
    xxl_job.callback_success(
        log_id=log_id,
        log_date_time=log_date_time,
        message="Task completed successfully.",
    )
```

## Configuration

| Key | Default | Description |
| --- | --- | --- |
| `XXL_JOB_ENABLED` | `True` | Enable the extension. |
| `XXL_JOB_ADMIN_ADDRESSES` | `[]` | List of XXL-JOB admin base URLs. |
| `XXL_JOB_ACCESS_TOKEN` | `""` | Access token; empty means no-token mode. |
| `XXL_JOB_EXECUTOR_APP_NAME` | `"flask-xxljob-executor"` | Executor application name. |
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | Address the admin uses to reach this executor. |
| `XXL_JOB_ROUTE_PREFIX` | `""` | URL prefix for the executor endpoints. |
| `XXL_JOB_AUTO_REGISTER` | `True` | Start automatic registration renewal. |
| `XXL_JOB_REGISTRY_INTERVAL` | `30` | Registration renewal interval (seconds). |
| `XXL_JOB_HTTP_CONNECT_TIMEOUT` | `3` | HTTP connect timeout (seconds). |
| `XXL_JOB_HTTP_READ_TIMEOUT` | `5` | HTTP read timeout (seconds). |
| `XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH` | `10000` | Max `handleMsg` length. |
| `XXL_JOB_MAX_REQUEST_SIZE` | `1048576` | Max request body size (bytes). |
| `XXL_JOB_MAX_PARAM_LENGTH` | `65536` | Max `executorParams` length. |

## CLI

```bash
flask --app "project:create_app" xxljob register
flask --app "project:create_app" xxljob remove
```

## Compatibility

Target support is `Flask >= 1.0` and `Python >= 3.8`. This release was verified locally on Python 3.8. Other combinations in the support matrix have not all been executed locally; run the test suite in your own environment before claiming a specific combination.

## Documentation

See the [docs](docs/) directory, including [getting-started.md](docs/getting-started.md) and [configuration.md](docs/configuration.md). Upgrading from an earlier version? See the [migration guide](docs/migration.md) and the [CHANGELOG](CHANGELOG.md).

## License

[MIT](LICENSE)

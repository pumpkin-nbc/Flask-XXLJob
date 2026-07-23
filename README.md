[English](README.md) | [简体中文](README.zh-CN.md)

# Flask-XXLJob

A Flask extension that implements the official [XXL-JOB](https://github.com/xuxueli/xxl-job) 2.4.1 executor protocol, so a Flask project can act as an XXL-JOB executor directly without a Java relay service.

Flask-XXLJob is a **protocol adapter**. It handles protocol integration and does **not** execute business tasks.

## Features

- Implements the official XXL-JOB 2.4.1 executor endpoints: `/beat`, `/idleBeat`, `/run`, `/kill`, `/log`.
- Exact, case-sensitive JobHandler dispatch through named `on_run("name")` callbacks.
- Executor registration / deregistration with automatic renewal.
- Task-result callback client (`callback`, `callback_success`, `callback_failure`).
- Access token support using the official `XXL-JOB-ACCESS-TOKEN` header.
- Multiple admin addresses with failover.
- Flask Application Factory support and per-application runtime isolation.
- Strict protocol string validation and startup detection of conflicting executor routes.
- Optional, isolated rotating-file and level-colored console plugin diagnostics.
- Minimal dependencies (`Flask`, `requests`), typed (`py.typed`).

## What it does not do

Flask-XXLJob never executes business tasks. It does not create thread pools, process pools, task queues, Celery tasks, or message queues; it does not manage task state, logs, timeouts, or cancellation; and it does not send the final task callback automatically. Your Flask project decides how to submit, execute, cancel, log, and finally call back.

## Installation

```bash
pip install Flask-XXLJob
```

## Five-minute quick start

New to Python, Flask, or XXL-JOB? Follow the step-by-step
[beginner's guide](docs/getting-started.md). It starts locally without requiring
XXL-JOB Admin.

```python
from flask import Flask
from flask_xxljob import FlaskXXLJob, XXLJobResponse

app = Flask(__name__)
app.config.update(
    XXL_JOB_AUTO_REGISTER=False,  # Start locally without Admin.
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
)
xxl_job = FlaskXXLJob(app)


@xxl_job.on_run("demoJobHandler")
def handle_run(request):
    print("job:", request.job_id, "params:", request.parse_params())
    return XXLJobResponse.success(content="job received")


app.run(port=5001)
```

Set the Admin job's JobHandler to exactly `demoJobHandler`. Flask-XXLJob
validates and dispatches it automatically; an unknown name returns an XXL-JOB
`code=500` response without calling another handler.

Save it as `app.py`, then run:

```bash
python app.py
```

The tested copy is available at
[`examples/beginner/app.py`](examples/beginner/app.py). Connect Admin only after
the local `/xxl-job/run` test succeeds.

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
| `XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH` | `10000` | Max `handleMsg` length (characters). |
| `XXL_JOB_MAX_REQUEST_SIZE` | `1048576` | Max request body size (bytes). |
| `XXL_JOB_MAX_PARAM_LENGTH` | `65536` | Max `executorParams` length (characters). |
| `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` | `100` | Max items per `callback_many` batch. |
| `XXL_JOB_ADMIN_RETRY_COUNT` | `0` | Same-address synchronous retries (capped). |
| `XXL_JOB_ADMIN_RETRY_BACKOFF` | `0.0` | Seconds between retries (capped). |
| `XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR` | `True` | Fail over on a non-200 status. |
| `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` | `False` | Fail over on invalid JSON. |
| `XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR` | `False` | Fail over on a business failure. |
| `XXL_JOB_LOG_ENABLED` | `False` | Enable plugin-managed diagnostic handlers. |
| `XXL_JOB_LOG_FILE_ENABLED` | `True` | Write managed logs to a rotating file. |
| `XXL_JOB_LOG_CONSOLE_ENABLED` | `True` | Write managed normal and error logs to the console. |
| `XXL_JOB_LOG_LEVEL` | `"INFO"` | Shared managed-handler level. |
| `XXL_JOB_LOG_FORMAT` | standard format | Shared Python Logging format. |
| `XXL_JOB_LOG_DATE_FORMAT` | `"%Y-%m-%d %H:%M:%S"` | Timestamp format. |
| `XXL_JOB_LOG_PATH` | `"./logs"` | File-log directory, relative to the process working directory. |
| `XXL_JOB_LOG_FILENAME` | `"flask-xxljob.log"` | File-log name. |
| `XXL_JOB_LOG_ENCODING` | `"utf-8"` | File encoding. |
| `XXL_JOB_LOG_MAX_BYTES` | `10485760` | Rotation size in bytes. |
| `XXL_JOB_LOG_BACKUP_COUNT` | `5` | Number of rotated backups. |
| `XXL_JOB_LOG_PROPAGATE` | `False` | Propagate records while managed handlers exist. |

Managed logging is off by default and creates no directory, file or console
handler. Enabling only `XXL_JOB_LOG_ENABLED` writes to
`./logs/flask-xxljob.log` and the console. For containers, disable the file
target and retain the default console target. See the
[logging guide](docs/logging.md).

## CLI

```bash
flask --app "project:create_app" xxljob register
flask --app "project:create_app" xxljob remove
flask --app "project:create_app" xxljob status
```

## Compatibility

Target support is `Flask >= 1.0` and `Python >= 3.8`. The compatibility matrix
(Python 3.8-3.14 x Flask 1/2/3) is configured in `tox.ini` and
`.github/workflows/ci.yml`. This release was verified locally on Python 3.12.13
with Flask 3.1.3; the remaining combinations are configured in CI but were not
executed locally. Run the test suite in your own environment before claiming a
specific combination.

When one `FlaskXXLJob` instance initializes multiple Flask applications, pass
`app=` to callback, registration, status and lifecycle helpers outside an
application context. Omitting it is supported only when exactly one application
has been initialized; pre-initialization `on_*` decorators remain default
handlers for every subsequently initialized application.

## Documentation

See the [docs](docs/) directory, including [getting-started.md](docs/getting-started.md), [configuration.md](docs/configuration.md), the [logging guide](docs/logging.md), the [API reference](docs/api-reference.md) and [integration testing](docs/integration-testing.md). For an end-to-end Flask template, use the [complete integration example](examples/complete_integration/README.md). Upgrading from an earlier version? See the [migration guide](docs/migration.md) and the [CHANGELOG](CHANGELOG.md).

## License

[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution information.

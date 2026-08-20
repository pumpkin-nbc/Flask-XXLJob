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
pip install flask-xxljob
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
| `XXL_JOB_ENABLED` | `True` | Master switch for executor routes and all Registry, Remove and Callback Admin traffic. |
| `XXL_JOB_ADMIN_ADDRESSES` | `[]` | List of XXL-JOB admin base URLs. |
| `XXL_JOB_ACCESS_TOKEN` | `""` | Access token; empty means no-token mode. |
| `XXL_JOB_EXECUTOR_APP_NAME` | `"flask-xxljob-executor"` | Executor application name. |
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | Executor service base URL (scheme/host/port). `XXL_JOB_ROUTE_PREFIX` is appended automatically. |
| `XXL_JOB_ROUTE_PREFIX` | `""` | URL prefix for the executor endpoints; also appended to `XXL_JOB_EXECUTOR_ADDRESS`. |
| `XXL_JOB_AUTO_REGISTER` | `True` | With `ENABLED=True`, prepare an activation-gated Registry Worker during initialization and activate it after Flask commit. |
| `XXL_JOB_DEREGISTER_ON_EXIT` | `False` | Best-effort background deregistration during Runtime shutdown. |
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
| `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` | `False` | Fail over on invalid JSON or an invalid response object. |
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
`./logs/flask-xxljob.log` and the console. The built-in rotating file target is
appropriate for a single process; multiple processes must not share that file.
For containers and multi-worker servers, prefer console or host-managed logs.
See the [logging guide](docs/logging.md).

`XXL_JOB_ENABLED=False` is a complete feature switch: the five executor routes
are not registered and Registry, Remove and Callback calls perform no Admin
HTTP. The local Runtime, status and CLI remain available, and synchronous APIs
return the existing disabled `CallResult`. Use `XXL_JOB_ENABLED=True` with
`XXL_JOB_AUTO_REGISTER=False` when a process needs Callback but not renewal.
Disabled initialization still validates local field types and logging, but does
not interpret unused Admin/executor URL strings or Route Prefix path syntax.

When enabled, Admin and non-empty executor URLs reject whitespace and control
characters, userinfo, query strings, fragments and invalid hosts/ports; only
HTTP/HTTPS is accepted. Route Prefix accepts root, an optional leading slash
and one trailing slash, but rejects dynamic converters, dot segments, repeated
slashes and URL/control syntax. Admin POST requests never follow redirects, and
malformed JSON objects are reported as `invalid_response`.

`init_app()` starts Registry only when `XXL_JOB_ENABLED` and
`XXL_JOB_AUTO_REGISTER` are both `True`. Set `XXL_JOB_AUTO_REGISTER=False` for
Gunicorn preload or an Application Factory shared with Celery, then call
`start_registry(app)` only in a process that should renew the executor. Each
Gunicorn worker still owns an independent process-local Registry lifecycle;
this release does not add leader election or cross-process locking. See
[deployment](docs/deployment.md).

With automatic Registry, register module-level handlers before `init_app()` to
minimize the short window in which Admin can see the executor before all
business handlers are ready. This is a recommendation, not a runtime readiness
check. Alternatively set `XXL_JOB_AUTO_REGISTER=False`, initialize the app,
register application handlers, and then call `start_registry(app)`.

`stop_registry()` now stops local renewal immediately and preserves the latest
`registered` snapshot. Use `stop_registry(remove=True)` for one best-effort
background Remove for that lifecycle, or use `stop_registry()` followed by
`remove_executor()` when a synchronous `CallResult` is required. Exit
deregistration is off by default so one worker does not remove a shared
executor identity.

Terminal cleanup is idempotent by cleanup responsibility, not permanently by
generation. A successful terminal Remove is reused by later shutdown or
synchronous terminal removal. If an accepted register subsequently recreates
the remote identity in the same generation, it creates a new cleanup
responsibility; strict RPC sequencing plus one Active and one optional Pending
fallback ensure that the newer remote state is removed exactly when needed.
Calling `remove_executor()` while renewal is still running remains an ordinary
one-shot RPC and does not stop or consume the lifecycle.

Every explicit `register_executor()` that enters the current generation before
lifecycle cleanup is linearized is counted before it waits for the Registry
network lock. Shutdown closes that coordination window without blocking and
defers its Remove until the already-counted calls finish. A later explicit
register is still a normal one-shot operation and is not permanently rejected.
Its real RPC completion is accepted by strict sequence and ProcessState
identity; generation and coordination ownership only decide whether that
accepted success changes lifecycle cleanup responsibility.
Generation zero is a manual cleanup scope only: an accepted explicit Register
does not create a Worker or start renewal, but exit cleanup can pair it with one
Remove when `XXL_JOB_DEREGISTER_ON_EXIT=True`. Its result cache never satisfies
the later generation-one Worker lifecycle.

Initialization first performs a side-effect-free preflight. Removed keys,
field values, automatic Registry completeness and route/Blueprint/CLI conflicts
are rejected before log handlers, files or Flask state are created. Private
prepare then starts an activation-gated daemon Thread, which makes no Admin
call, and creates only a detachable finalizer handle; neither resource publishes
`app.extensions`, the application registry, CLI, routes or hooks. Flask commit
publishes the reversible state before registering the Blueprint/hooks, and only
the Prepared creator may then commit the generation/Worker and wake the Thread.
A preparation failure detaches the finalizer, cancels a started Prepared Thread,
removes only state still owned by that initialization, closes its managed log
handlers and preserves the original error. A committed Worker still runs its
lifecycle `finally`, even if stopped before its first Registry RPC. This is
targeted private-resource atomicity, not a general rollback of arbitrary Flask
route or hook mutations.

## CLI

```bash
flask --app "project:create_app" xxljob register
flask --app "project:create_app" xxljob remove
flask --app "project:create_app" xxljob status
```

The CLI `remove` command is terminal for the current renewal lifecycle: it
stops the local Registry Worker before attempting synchronous deregistration.
The Worker remains stopped even when Admin removal fails. The low-level
`remove_executor()` API remains a one-shot RPC and does not stop renewal.

## Compatibility

Target support is `Flask >= 1.0` and `Python >= 3.8`. The compatibility matrix
(Python 3.8-3.14 x Flask 1/2/3) is configured in
`.github/workflows/ci.yml`. This release was verified locally on Python 3.12.13
with Flask 3.1.3; the remaining combinations are configured in CI but were not
executed locally. Run the test suite in your own environment before claiming a
specific combination. Final local 0.4.0 test and coverage results are recorded
in the changelog.

When one `FlaskXXLJob` instance initializes multiple Flask applications, pass
`app=` to callback, registration, status and lifecycle helpers outside an
application context. Omitting it is supported only when exactly one application
has been initialized; pre-initialization `on_*` decorators remain default
handlers for every subsequently initialized application.

## Documentation

See the [docs](docs/) directory, including [getting-started.md](docs/getting-started.md), [configuration.md](docs/configuration.md), the [logging guide](docs/logging.md), the [API reference](docs/api-reference.md) and [integration testing](docs/integration-testing.md). For an end-to-end Flask template, use the [complete integration example](examples/complete_integration/README.md). Upgrading from an earlier version? See the [migration guide](docs/migration.md) and the [CHANGELOG](CHANGELOG.md).

## License

[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution information.

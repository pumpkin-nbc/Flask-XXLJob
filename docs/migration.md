[English](migration.md) | [简体中文](migration.zh-CN.md)

# Migration from the Java relay

Previously, Python tasks were reached through a Java executor service:

```text
XXL-JOB -> Java executor -> Java calls Python HTTP -> Python runs task
```

With Flask-XXLJob the Flask project is the executor directly:

```text
XXL-JOB -> Flask (Flask-XXLJob) -> your on_run submits the task
```

## Steps

1. Add `Flask-XXLJob` to your dependencies and initialize the extension in your factory.
2. Point `XXL_JOB_EXECUTOR_ADDRESS` at the Flask service and keep the same `XXL_JOB_ACCESS_TOKEN` as the Java executor used.
3. Move the logic that submitted tasks in the Java layer into your `on_run` callback, calling your existing task service.
4. Replace the Java-side final status update with a `callback_success` / `callback_failure` call from your task worker.
5. Register the executor with the same app name so existing job bindings keep working.

## Notes

Job routing, block strategies, timeouts and retries are still managed by the
XXL-JOB admin. Flask-XXLJob only relays the protocol; your task service keeps
full control over execution.

## Upgrading 0.3.2 to 0.3.3

`0.3.3` lets success responses carry an optional message as the first argument:

```python
return XXLJobResponse.success("job queued")
return XXLJobResponse.success(msg="job queued", content="accepted")
```

```bash
pip install --upgrade flask-xxljob==0.3.3
```

## Upgrading 0.3.1 to 0.3.2

`0.3.2` always appends `XXL_JOB_ROUTE_PREFIX` to `XXL_JOB_EXECUTOR_ADDRESS`
when the configuration is loaded. Set the executor address to the service base
URL only:

```python
app.config.update(
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
)
# Registered address becomes http://127.0.0.1:5001/xxl-job
```

Do not include the route prefix in `XXL_JOB_EXECUTOR_ADDRESS`; values such as
`http://127.0.0.1:5001/xxl-job` with `XXL_JOB_ROUTE_PREFIX="/xxl-job"` become
`http://127.0.0.1:5001/xxl-job/xxl-job`.

```bash
pip install --upgrade flask-xxljob==0.3.2
```

## Upgrading 0.3.0 to 0.3.1

`0.3.1` changes only release metadata and publishing configuration. The
distribution name now uses its normalized lowercase spelling; public Python
imports and runtime APIs are unchanged.

```bash
pip install --upgrade flask-xxljob==0.3.1
```

## Upgrading 0.2.1 to 0.3.0

0.3.0 changes Run registration to explicit JobHandler dispatch. Replace:

```python
@xxl_job.on_run
def handle_run(request):
    ...
```

with one or more named handlers:

```python
@xxl_job.on_run("demoJobHandler")
def handle_demo(request):
    ...

@xxl_job.on_run("reportJobHandler")
def handle_report(request):
    ...
```

The Admin JobHandler must match exactly, including capitalization. There is no
unnamed fallback. Application-level calls change to
`set_run_callback(app, "name", func)`, `get_run_callback(app, "name")` and
`register_callbacks(app, run={"name": func})`.

0.3.0 also removes ambiguous application selection outside a Flask application
context. If an extension instance has initialized exactly one app, helpers may
still omit `app`. Once it has initialized multiple apps, callback, registration,
status and registry-lifecycle helpers must receive `app` explicitly. Calls made
inside an application context are unchanged.

Pre-initialization `on_*` decorators still seed every application initialized
later, and public imports remain unchanged. Package metadata, `__version__` and
the CLI now all read the same internal version source.

### Upgrade

```bash
pip install --upgrade flask-xxljob==0.3.0
```

### Rollback

```bash
pip install flask-xxljob==0.2.1
```

## Upgrading 0.2.0 to 0.2.1

0.2.1 is a stability release. Protocol string fields now reject non-string
values, conflicting executor `POST` routes fail during initialization before
the app is partially configured, and a timed-out registry shutdown completes
its requested deregistration after an in-flight renewal returns. Access tokens
containing only whitespace are treated as empty, and Admin/executor URLs receive
strict scheme, host and port validation while context paths remain supported.

Existing valid payloads and configurations require no changes. If application
code constructs `TriggerRequest`, `CallbackRequest` or `RegistryRequest` with
numbers, booleans, arrays or objects in string fields, convert those values to
strings explicitly before upgrading.

### Upgrade

```bash
pip install --upgrade flask-xxljob==0.2.1
```

### Rollback

```bash
pip install flask-xxljob==0.2.0
```

## Upgrading 0.1.2 to 0.2.0

0.2.0 is a backward-compatible minor release. It adds application-level callback
registration, batch callbacks, a configurable synchronous Admin retry/failover
policy, plugin status querying and a `xxljob status` CLI command, richer
`CallResult` fields, constant-time access-token comparison, and a public
exception hierarchy. All 0.1.2 public APIs, imports and configuration keys keep
working unchanged.

### Do I need to change my code or config?

No. Every new feature is opt-in, and the new configuration keys default to
0.1.2-compatible behaviour:

- App-level registration: `register_callbacks`, `set_*_callback(replace=...)`,
  `get_*_callback`. The `on_*` decorators still work.
- Batch callback: `callback_many(...)`. Single `callback*` methods are unchanged.
- Admin call policy (defaults keep 0.1.2 behaviour): `XXL_JOB_ADMIN_RETRY_COUNT`
  (0), `XXL_JOB_ADMIN_RETRY_BACKOFF` (0.0), `XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR`
  (True), `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` (False),
  `XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR` (False),
  `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` (100).
- Status: `get_status(app=None)` returns an `XXLJobStatus`; `start_registry` /
  `stop_registry` control the registry thread.
- Exceptions: `FlaskXXLJobError` is the new base; all previous names remain as
  aliases, so existing `except XXLJobError` / `except XXLJobConfigError` keep
  working.

### Upgrade

```bash
pip install --upgrade flask-xxljob==0.2.0
```

### Rollback

```bash
pip install flask-xxljob==0.1.2
```

## Upgrading 0.1.1 to 0.1.2

0.1.2 is a backward-compatible patch release. It focuses on protocol
re-verification, registration and callback reliability, clearer configuration
validation, and expanded tests and bilingual docs. There are no breaking API
changes, and the 0.1.1 usage patterns continue to work unchanged.

### Do I need to change my code or config?

No. All 0.1.1 public APIs, imports and configuration keys are unchanged. The
only additive change is an optional `error_type` category on the call result
returned by `register_executor`, `remove_executor` and the `callback*` methods,
which lets you distinguish failures (`network`, `timeout`, `http`,
`invalid_json`, `business`, `config`) without inspecting the underlying
`requests` objects. Reading it is optional.

### Upgrade

```bash
pip install --upgrade flask-xxljob==0.1.2
```

### Verify

1. Check the installed version: `python -c "import flask_xxljob; print(flask_xxljob.__version__)"` prints `0.1.2`.
2. Start your Flask service (or one of the `examples/`).
3. Confirm `POST /beat` returns `{"code": 200, ...}`.
4. Confirm the executor registers (admin online machines list, or call `register_executor`).
5. Confirm `POST /run` reaches your `on_run` callback.
6. Confirm a `callback_success` / `callback_failure` call after your task finishes.

### Rollback

```bash
pip install flask-xxljob==0.1.1
```

Business task execution stays in your Flask project; Flask-XXLJob never runs the
task itself.

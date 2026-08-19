[English](api-reference.md) | [简体中文](api-reference.zh-CN.md)

# API reference

This page documents the public API of Flask-XXLJob 0.4.0. The extension only
adapts the XXL-JOB 2.4.1 protocol; it never executes business tasks.

## `FlaskXXLJob`

The main extension class.

```python
from flask_xxljob import FlaskXXLJob

xxl_job = FlaskXXLJob()          # deferred init
xxl_job.init_app(app)            # or FlaskXXLJob(app)
```

### Request-callback registration (decorators)

`on_run(executor_handler)` registers a named, extension-level Run handler.
Names must be non-empty strings without leading or trailing whitespace and are
matched exactly and case-sensitively. Other `on_*` decorators remain unnamed.
Handlers registered before initialization are seeded into every later app.

```python
@xxl_job.on_run("demoJobHandler")
def handle_run(request):
    return XXLJobResponse.success()

# also: on_idle_beat, on_kill, on_log
```

### Application-level registration

Register or read handlers for a specific application. `app=None` uses the current
application context. Outside a context it is accepted when exactly one app has
been initialized; with multiple initialized apps, pass `app` explicitly or an
`XXLJobError` is raised.

```python
xxl_job.register_callbacks(
    app,
    run={"demoJobHandler": handle_run, "reportJobHandler": handle_report},
    replace=False,
)
xxl_job.set_run_callback(app, "demoJobHandler", handle_run, replace=True)
handler = xxl_job.get_run_callback(app, "demoJobHandler")
# also: set_idle_beat_callback / set_kill_callback / set_log_callback
#       get_idle_beat_callback / get_kill_callback / get_log_callback
```

An invalid name, non-callable value, or duplicate name raises
`XXLJobCallbackRegistrationError` unless a duplicate uses `replace=True`.
`register_callbacks` validates the full batch before changing the registry.
An unmatched request returns HTTP 200 with XXL-JOB `code=500` and
`Unsupported JobHandler: <name>`; no fallback Run handler exists.

### Executor registration

```python
result = xxl_job.register_executor(app)   # CallResult
result = xxl_job.remove_executor(app)     # CallResult
```

Both are synchronous one-shot Admin operations. They share the current
process's Registry network lock but do not start or stop a lifecycle, advance a
lifecycle generation, or consume automatic Remove eligibility. A failed call
preserves the existing `registered` snapshot. When the extension is disabled,
both return a local config-failure `CallResult` without an Admin RPC.

### Task-result callbacks

```python
xxl_job.callback(log_id, log_date_time, handle_code, handle_msg=None, app=None)
xxl_job.callback_success(log_id, log_date_time, message=None, app=None)
xxl_job.callback_failure(log_id, log_date_time, message=None, app=None)
xxl_job.callback_many(callbacks, app=None)   # list of CallbackRequest or dict
```

`callback_many` validates every item before sending, never auto-splits, and
rejects the whole batch (sending nothing) if any item is invalid or the count
exceeds `XXL_JOB_CALLBACK_BATCH_MAX_SIZE`.

### Status and lifecycle

```python
status = xxl_job.get_status(app)   # XXLJobStatus
xxl_job.start_registry(app)
xxl_job.stop_registry(app)                  # Local stop; immediate return.
xxl_job.stop_registry(app, remove=True)     # Add one background Remove.
```

`start_registry()` validates complete Registry configuration, creates at most
one current daemon renewal Worker for the process, and returns before its first
Admin call completes. `stop_registry()` has a keyword-only `remove=False`
default: it immediately detaches and wakes that Worker, does not join or access
Admin, and preserves the latest `registered` snapshot. Consequently
`registry_thread_running=False` and `registered=True` is valid.

`stop_registry(remove=True)` first validates configuration, performs the same
local stop, and schedules at most one background `registryRemove` for that
lifecycle generation. To obtain a deterministic synchronous result, use:

```python
xxl_job.stop_registry(app)
result = xxl_job.remove_executor(app)
```

All Registry state is process-local. Every local read first checks the PID; a
forked child gets blank locks, Worker/Remove ownership, sequences and snapshots
without acquiring a parent lock. Status reads never access Admin or create a
thread. Periodic renewal remains immediate registration followed by
`REGISTRY_INTERVAL` waits.

## Request models

Passed to your handlers; all fields are typed and Unicode-safe. Protocol string
fields accept only strings; a missing value or `None` uses that field's default.
Numbers, booleans, arrays and objects are rejected: executor endpoints return an
XXL-JOB `code=500` response, while outgoing callback APIs raise
`XXLJobValidationError` before sending.

```python
from flask_xxljob import (
    TriggerRequest, IdleBeatRequest, KillRequest, LogRequest, RegistryRequest,
    CallbackRequest,
)
```

## Response models

```python
from flask_xxljob import XXLJobResponse, LogResponse

XXLJobResponse.success(msg=None, content=None)
XXLJobResponse.failure("message")
```

## `CallResult` / `AdminCallResult`

The result of a single admin API call (`AdminCallResult` is an alias).

```python
result.success        # bool
result.code           # Optional[int]  business code from the admin
result.msg            # Optional[str]
result.message        # msg or, if absent, error
result.address        # admin address that produced the result
result.admin_address  # alias of address
result.error          # local error string (never contains the token)
result.error_type     # None | 'network' | 'timeout' | 'http'
                      #      | 'invalid_json' | 'business' | 'config'
result.attempt_count  # total HTTP attempts made
result.elapsed_ms     # total elapsed milliseconds
result.http_status    # last HTTP status code, if any
```

## `XXLJobStatus`

A read-only snapshot of the plugin (never the token or business-task state).

```python
status.enabled
status.auto_register
status.registered
status.last_registry_time
status.last_registry_success
status.last_registry_admin_address
status.last_registry_error_type
status.last_registry_message
status.registry_thread_running
status.log_enabled
status.log_level
status.log_file_enabled
status.log_console_enabled
status.log_file
```

Logging fields describe the effective managed targets. `log_file` is the
resolved absolute path when file logging is active, otherwise `None`. Status
and CLI output never include the access token and cannot modify logging.

## Exceptions

All exceptions inherit from `FlaskXXLJobError`. Previous names remain as aliases.

```python
from flask_xxljob import (
    FlaskXXLJobError,            # base
    XXLJobError,                # alias of FlaskXXLJobError
    XXLJobConfigurationError,   # XXLJobConfigError (alias)
    XXLJobInitializationError,
    XXLJobAlreadyInitializedError,
    XXLJobCallbackRegistrationError,
    XXLJobValidationError,      # XXLJobRequestError (alias)
    XXLJobProtocolError,
    XXLJobAdminCallError,
    XXLJobCallbackError,
    XXLJobRegistryError,
)
```

## CLI

```bash
flask xxljob register
flask xxljob remove
flask xxljob status
```

`xxljob remove` first stops the current local Registry renewal lifecycle and
then performs one synchronous Remove. A failed Admin Remove produces a non-zero
exit code but never restarts renewal. This terminal CLI behavior is deliberately
different from the public low-level `remove_executor()`, which performs only
one synchronous RPC and does not stop a Worker.

See [configuration](configuration.md) for the full list of configuration keys.

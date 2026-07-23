[English](api-reference.md) | [简体中文](api-reference.zh-CN.md)

# API reference

This page documents the public API of Flask-XXLJob 0.3.0. The extension only
adapts the XXL-JOB 2.4.1 protocol; it never executes business tasks.

## `FlaskXXLJob`

The main extension class.

```python
from flask_xxljob import FlaskXXLJob

xxl_job = FlaskXXLJob()          # deferred init
xxl_job.init_app(app)            # or FlaskXXLJob(app)
```

### Request-callback registration (decorators)

The `on_*` decorators register the default (extension-level) handlers, which are
seeded into every application initialized afterwards.

```python
@xxl_job.on_run
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
xxl_job.register_callbacks(app, run=handle_run, replace=False)
xxl_job.set_run_callback(app, handle_run, replace=True)
handler = xxl_job.get_run_callback(app)
# also: set_idle_beat_callback / set_kill_callback / set_log_callback
#       get_idle_beat_callback / get_kill_callback / get_log_callback
```

Registering the same handler twice raises `XXLJobCallbackRegistrationError`
unless `replace=True`.

### Executor registration

```python
result = xxl_job.register_executor(app)   # CallResult
result = xxl_job.remove_executor(app)     # CallResult
```

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
xxl_job.stop_registry(app)
```

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

XXLJobResponse.success(content=None)
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
```

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

See [configuration](configuration.md) for the full list of configuration keys.

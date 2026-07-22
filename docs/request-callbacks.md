[English](request-callbacks.md) | [简体中文](request-callbacks.zh-CN.md)

# Request Callbacks

Flask-XXLJob does not use an executor adapter. Instead you register plain
functions that receive typed request models. These functions are XXL-JOB
request handlers, not business task handlers.

## Registration

Each of the four callbacks can be used as a method or a decorator:

```python
@xxl_job.on_run
def handle_run(request):
    task_id = project_task_service.submit(
        task_name=request.executor_handler,
        task_params=request.executor_params,
        job_id=request.job_id,
        log_id=request.log_id,
        log_date_time=request.log_date_time,
    )
    if task_id is None:
        return XXLJobResponse.failure("submit task failed")
    return XXLJobResponse.success()


@xxl_job.on_idle_beat
def handle_idle_beat(request):
    if project_task_service.is_running(request.job_id):
        return XXLJobResponse.failure("job is running")
    return XXLJobResponse.success()


@xxl_job.on_kill
def handle_kill(request):
    if not project_task_service.cancel(request.job_id):
        return XXLJobResponse.failure("kill task failed")
    return XXLJobResponse.success()


@xxl_job.on_log
def handle_log(request):
    return project_task_service.read_log(
        log_id=request.log_id,
        from_line_num=request.from_line_num,
    )
```

## Registration timing

Callbacks may be registered either before or after `init_app`. Registering at
module level (before `init_app`) is fully supported and is the recommended form
for the application factory pattern:

```python
xxl_job = FlaskXXLJob()

@xxl_job.on_run
def handle_run(request):
    return XXLJobResponse.success()

def create_app():
    app = Flask(__name__)
    xxl_job.init_app(app)
    return app
```

Module-level callbacks become the defaults for every application initialized by
the extension.

## Application-level registration

In addition to the `on_*` decorators you can register handlers for a specific
application. This is useful with the application factory or multiple apps:

```python
def create_app():
    app = Flask(__name__)
    xxl_job.init_app(app)
    xxl_job.register_callbacks(app, run=handle_run, log=handle_log)
    # or: xxl_job.set_run_callback(app, handle_run, replace=True)
    return app
```

Read the currently registered handler with `get_run_callback(app)` (and the
`idle_beat`/`kill`/`log` variants). When `app=None`, the current application
context or the most recently initialized application is used.

Resolution priority when dispatching a request: the application-specific
registry is checked first, then the extension-level defaults set by the `on_*`
decorators. If neither is configured, the endpoint returns the standard
not-configured failure.

## Duplicate registration

Registering the same callback twice raises `XXLJobCallbackRegistrationError`
(a subclass of `FlaskXXLJobError`). Pass `replace=True` to
`register_callbacks`/`set_*_callback` to intentionally override an existing
handler.

## Return values

`on_run`, `on_idle_beat` and `on_kill` return an `XXLJobResponse`. `on_log`
returns a `LogResponse`. Any other return type (including `None`, `dict`, `str`
or `bool`) produces an explicit "unsupported response type" failure rather than
an internal error.

## Unconfigured callbacks

If a callback is not registered, the corresponding endpoint returns an explicit
failure such as `XXL-JOB run callback is not configured`; it never silently
returns success.

## Parameters

`TriggerRequest.parse_params()` parses `executor_params` without mutating it: a
blank value returns `None`, valid JSON returns the parsed object, otherwise the
raw string is returned.

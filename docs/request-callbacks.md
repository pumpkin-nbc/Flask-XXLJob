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

## Return values

`on_run`, `on_idle_beat` and `on_kill` return an `XXLJobResponse`. `on_log`
returns a `LogResponse`.

## Unconfigured callbacks

If a callback is not registered, the corresponding endpoint returns an explicit
failure such as `XXL-JOB run callback is not configured`; it never silently
returns success.

## Parameters

`TriggerRequest.parse_params()` parses `executor_params` without mutating it: a
blank value returns `None`, valid JSON returns the parsed object, otherwise the
raw string is returned.

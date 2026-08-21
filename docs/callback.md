[English](callback.md) | [简体中文](callback.zh-CN.md)

# Task-Result Callback

Flask-XXLJob never decides when a task completes and never sends the final
callback automatically. When your task finishes, your project actively calls
the callback API.

## API

```python
xxl_job.callback_success(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    message="Task completed successfully.",
)

xxl_job.callback_failure(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    message="Task execution failed.",
)

xxl_job.callback(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    handle_code=200,
    handle_msg="Task completed successfully.",
)
```

## Batch callback

To report several task results in one official request, use `callback_many`:

```python
from flask_xxljob import CallbackRequest

xxl_job.callback_many(
    [
        CallbackRequest(log_id=1, log_date_time=1710000000000, handle_code=200),
        CallbackRequest(log_id=2, log_date_time=1710000000000, handle_code=500,
                        handle_msg="failed"),
    ],
    app=app,
)
```

Every item is validated before anything is sent. The batch is never auto-split,
and if any item is invalid or the count exceeds `XXL_JOB_CALLBACK_BATCH_MAX_SIZE`
the whole batch is rejected (all-or-nothing) and nothing is delivered.

## Within an application context

Inside a Flask application context the `app` argument can be omitted:

```python
with app.app_context():
    xxl_job.callback_success(
        log_id=log_id,
        log_date_time=log_date_time,
        message="Task completed successfully.",
    )
```

## Behaviour

The callback client builds the official request (a single-element
`HandleCallbackParam` array sent to `/api/callback`), carries the access token,
applies connect and read timeouts, truncates `handleMsg` to the configured
maximum length, and returns an explicit result. It does not persist callbacks,
retry indefinitely in the background, or create background threads.

`message` defaults to `None` (treated as an empty message). `log_id` and
`log_date_time` must be integers; passing a boolean or non-integer raises
`XXLJobRequestError`.

When several admin addresses are configured, the callback stops at the first
address that returns a valid business response (success or failure) to avoid
delivering the same callback twice; it only fails over to the next address on a
network error, a non-200 status, invalid JSON, or an invalid response object.
Admin POST never follows redirects. Parsed bodies must be objects whose `code`
is a non-boolean integer and whose `msg` is a string or `None`; only `code=200`
is successful. The returned `CallResult`
(also exported as `AdminCallResult`) exposes `success`, `code`, `msg`/`message`,
`address`/`admin_address` and `error_type`. `error_type` classifies failures as
one of `network`, `timeout`, `http`, `invalid_json`, `invalid_response`,
`business` or `config`
(and is `None` on success), so you can react without inspecting `requests`. The
result also carries `attempt_count`, `elapsed_ms` and `http_status` for
troubleshooting. Failover and bounded synchronous retry are controlled by the
`XXL_JOB_ADMIN_*` configuration keys; by default business failures are not
re-sent to another admin.

`XXL_JOB_ENABLED=False` is the complete feature switch. All four public
callback forms return the local disabled `CallResult` and send no Admin HTTP.
They still resolve the target application Runtime first; missing initialization
and ambiguous multi-app selection therefore remain errors. Once that Runtime is
known to be disabled, the callback body is not validated, normalized, copied or
iterated. Enabled message conversion, validation and truncation remain exactly
as before.
Use `XXL_JOB_ENABLED=True` with `XXL_JOB_AUTO_REGISTER=False` for a process that
needs callbacks but should not maintain Registry renewal.

## Long-running tasks (Celery and similar)

Flask-XXLJob does not run or time out your business work. For Celery or any
other async worker:

1. In `on_run`, enqueue the job quickly and return `XXLJobResponse.success(...)`.
   Pass `log_id` and `log_date_time` into the worker unchanged.
2. When the worker finishes, call `callback_success` / `callback_failure` (with a
   Flask application context when needed).
3. In XXL-JOB Admin, set the job **timeout** (seconds) higher than the longest
   expected worker runtime. If Admin marks the run as
   “任务结果丢失，标记失败”, the callback arrived too late or never arrived —
   raise the Admin timeout and verify the worker callback succeeded
   (`CallResult.success`).

## Out of scope

Reliable callback delivery beyond the bounded Admin HTTP client is the host
application’s responsibility. Flask-XXLJob does **not** provide a callback
outbox, durable queue, or background infinite retry. If `callback_*` fails,
inspect `CallResult` and retry or persist from your own task/worker layer.

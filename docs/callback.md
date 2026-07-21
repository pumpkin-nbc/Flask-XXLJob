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
maximum length, tries multiple admin addresses in order, and returns an
explicit result. It does not persist callbacks, retry indefinitely in the
background, or create background threads.

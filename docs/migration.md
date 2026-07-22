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
pip install --upgrade Flask-XXLJob==0.1.2
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
pip install Flask-XXLJob==0.1.1
```

Business task execution stays in your Flask project; Flask-XXLJob never runs the
task itself.

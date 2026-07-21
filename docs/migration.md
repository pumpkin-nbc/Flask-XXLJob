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

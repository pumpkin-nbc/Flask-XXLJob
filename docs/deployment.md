[English](deployment.md) | [简体中文](deployment.zh-CN.md)

# Deployment

## Executor address

Set `XXL_JOB_EXECUTOR_ADDRESS` to a URL the XXL-JOB admin can reach. In
containerized or multi-host deployments this is usually the service address,
not `127.0.0.1`. Set only the service base URL; `XXL_JOB_ROUTE_PREFIX` is
appended automatically when the configuration is loaded.

## Job timeout for long-running work

Task timeout is configured in XXL-JOB Admin (per job, in seconds), not in
Flask-XXLJob. For Celery or other async workers, raise that timeout above the
longest expected runtime, and have the worker call `callback_success` /
`callback_failure` when finished. See [Task-Result Callback](callback.md).

## Automatic registration

With `XXL_JOB_AUTO_REGISTER=True` the extension starts a daemon thread that
registers the executor and renews it every `XXL_JOB_REGISTRY_INTERVAL` seconds.
Registration failures are logged and never crash the application.

## Flask debug reloader

Under the Flask debug reloader the registration thread only starts in the
reloader child process (where `WERKZEUG_RUN_MAIN=true`), so it is not started
twice.

## Multiple processes

Each worker process that initializes the extension registers with the same
executor app name and address. Because the registry key is the address, running
several workers behind one address is fine; running workers with different
addresses registers multiple executor instances. Plan your process model
accordingly.

For plugin diagnostics in containers, prefer console-only output and let the
platform collect, retain and rotate logs:

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
)
```

The standard `RotatingFileHandler` is process-local and does not make a shared
file safe for multiple Gunicorn or other worker processes. Use separate files,
host-managed Logging, or console aggregation instead. See [Logging](logging.md).

## Manual registration

You can disable auto-registration and register from the CLI instead:

```bash
flask --app "project:create_app" xxljob register
```

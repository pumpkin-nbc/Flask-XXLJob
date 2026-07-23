[English](logging.md) | [简体中文](logging.zh-CN.md)

# Logging

Flask-XXLJob records plugin diagnostics such as initialization, registration,
renewal, deregistration, Admin failover, callbacks and protocol failures. It
does not record business-task output. Managed logging is disabled by default,
creates no directory or file, and adds no console handler.

## Output modes

File only (also the result of setting only `XXL_JOB_LOG_ENABLED=True`):

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_ENABLED=False,
)
```

Console only:

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_STREAM="stderr",
)
```

File and console together:

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
)
```

If both targets are disabled, or the total switch is off, Flask-XXLJob leaves
the runtime logger's level and propagation unchanged. The host can then attach
a handler to `flask_xxljob` using ordinary Python Logging. The package
`NullHandler` prevents unwanted default output but does not block propagation
to a host handler.

## Files, formatting and rotation

Relative `XXL_JOB_LOG_PATH` values resolve from the process current working
directory. `XXLJobStatus.log_file` reports the resulting absolute path.
File and console handlers share `XXL_JOB_LOG_LEVEL`, `XXL_JOB_LOG_FORMAT` and
`XXL_JOB_LOG_DATE_FORMAT`. The level, encoding, stream, rotation values and
format are strictly validated during `init_app()`.

Each Flask runtime owns a unique `flask_xxljob.app.<app>.<sequence>.<component>`
logger hierarchy. Even same-named Flask apps remain isolated. The extension
never changes the root logger or `app.logger`, removes only its own marked
handlers, and closes them automatically when the app is collected or the
interpreter exits. Console cleanup never closes `sys.stdout` or `sys.stderr`.

When a managed target exists, `XXL_JOB_LOG_PROPAGATE=False` prevents duplicate
host output by default. Set it to `True` only when both managed and host
handlers should receive each record.

## Sensitive data

Plugin events contain safe context, result categories, HTTP status and
exception types. They do not include request bodies or headers, Access Tokens,
`executorParams`, `glueSource`, `handleMsg`, or user exception messages. A
final filter on every managed handler redacts recognized credentials and
private-key text even at `DEBUG`.

This is defense in depth, not permission to send arbitrary business data to
the plugin logger. Configure application business logs separately.

## Containers and multiple processes

For Docker, Kubernetes, Gunicorn, systemd and similar environments, prefer:

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_STREAM="stdout",
)
```

Let the platform collect, retain, search and rotate that stream. Python's
standard `RotatingFileHandler` does not guarantee safe shared-file rotation
across multiple worker processes. Use console aggregation, a host-managed
handler, or a separate file per process when running multiple workers.

The complete list of options is in [Configuration](configuration.md).

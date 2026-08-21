[English](logging.md) | [简体中文](logging.zh-CN.md)

# Logging

Flask-XXLJob records plugin diagnostics such as initialization, registration,
renewal, deregistration, Admin failover, callbacks and protocol failures. It
does not record business-task output. Managed logging is disabled by default,
creates no directory or file, and adds no console handler.

## Output modes

File only:

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

Because file and console outputs both default to enabled, setting only
`XXL_JOB_LOG_ENABLED=True` selects the third mode. The console handler uses the
standard Python Logging console stream and emits both normal and error records
that meet `XXL_JOB_LOG_LEVEL`; there is no separate stream configuration.

## Console colors

Managed console records use ANSI colors by level:

| Level | Color |
| --- | --- |
| `DEBUG` | blue |
| `INFO` | green |
| `WARNING` | yellow |
| `ERROR` | red |
| `CRITICAL` | bold red |

The color wraps the complete formatted console record and is reset immediately
after it. File logs remain plain text without ANSI escape sequences. Coloring
does not change level filtering, formatting fields or sensitive-data redaction.
The terminal must support ANSI colors to render them visually.

If both targets are disabled, or the total switch is off, Flask-XXLJob leaves
the runtime logger's level and propagation unchanged. The host can then attach
a handler to `flask_xxljob` using ordinary Python Logging. The package
`NullHandler` prevents unwanted default output but does not block propagation
to a host handler.

## Files, formatting and rotation

Relative `XXL_JOB_LOG_PATH` values resolve from the process current working
directory. `XXLJobStatus.log_file` reports the resulting absolute path.
File and console handlers share `XXL_JOB_LOG_LEVEL`, `XXL_JOB_LOG_FORMAT` and
`XXL_JOB_LOG_DATE_FORMAT`; the console then adds its level color around that
formatted text. The level, encoding, rotation values and format are strictly
validated during `init_app()`.

Each Flask runtime owns a unique `flask_xxljob.app.<app>.<sequence>.<component>`
logger hierarchy. Even same-named Flask apps remain isolated. The extension
never changes the root logger or `app.logger`, removes only its own marked
handlers, and closes them automatically when the app is collected or the
interpreter exits. Console cleanup never closes `sys.stdout` or `sys.stderr`.

When a managed target exists, `XXL_JOB_LOG_PROPAGATE=False` prevents duplicate
host output by default. Set it to `True` only when both managed and host
handlers should receive each record.

## Sensitive data

Plugin-authored events contain safe context, result categories and HTTP status.
They do not deliberately include request bodies or headers, Access Tokens,
`executorParams`, `glueSource`, or `handleMsg`. A final filter on every managed
handler redacts recognized credentials and private-key text even at `DEBUG`.

Exceptions raised by user callbacks or unexpected package defects retain their
type, message and full traceback in local logs. Expected network, HTTP and
remote business failures remain concise `CallResult` events and do not emit a
traceback on every Registry interval. Traceback details never enter executor
HTTP responses.

This is defense in depth, not permission to send arbitrary business data to
the plugin logger. Application code must not put passwords, tokens, private
keys or other credentials into exception messages. Configure application
business logs separately.

## Containers and multiple processes

For Docker, Kubernetes, Gunicorn, systemd and similar environments, prefer:

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
)
```

Let the platform collect, retain, search and rotate that stream. Python's
standard `RotatingFileHandler` does not guarantee safe shared-file rotation
across multiple worker processes. The built-in file target is intended for a
single process. Use console aggregation, a host-managed multi-process-safe
handler, or a separate file per process when running multiple workers.

The complete list of options is in [Configuration](configuration.md).

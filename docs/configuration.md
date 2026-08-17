[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# Configuration

All configuration is read from `app.config` during `init_app()`. The extension
never reads configuration at import time and never accesses `current_app` in
the constructor.

## Keys

| Key | Default | Description |
| --- | --- | --- |
| `XXL_JOB_ENABLED` | `True` | Enable the extension. |
| `XXL_JOB_ADMIN_ADDRESSES` | `[]` | List of XXL-JOB admin base URLs. |
| `XXL_JOB_ACCESS_TOKEN` | `""` | Access token; empty means no-token mode. |
| `XXL_JOB_EXECUTOR_APP_NAME` | `"flask-xxljob-executor"` | Executor application name. |
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | Executor service base URL (scheme/host/port). `XXL_JOB_ROUTE_PREFIX` is appended automatically. |
| `XXL_JOB_ROUTE_PREFIX` | `""` | URL prefix for the executor endpoints; also appended to `XXL_JOB_EXECUTOR_ADDRESS`. |
| `XXL_JOB_AUTO_REGISTER` | `True` | With `ENABLED=True`, start Registry after `init_app()` completes. |
| `XXL_JOB_DEREGISTER_ON_EXIT` | `False` | Request best-effort background removal during Runtime shutdown. |
| `XXL_JOB_REGISTRY_INTERVAL` | `30` | Registration renewal interval (seconds). |
| `XXL_JOB_HTTP_CONNECT_TIMEOUT` | `3` | HTTP connect timeout (seconds). |
| `XXL_JOB_HTTP_READ_TIMEOUT` | `5` | HTTP read timeout (seconds). |
| `XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH` | `10000` | Max `handleMsg` length (characters). |
| `XXL_JOB_MAX_REQUEST_SIZE` | `1048576` | Max request body size (bytes). |
| `XXL_JOB_MAX_PARAM_LENGTH` | `65536` | Max `executorParams` length (characters). |
| `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` | `100` | Max items per `callback_many` batch. |
| `XXL_JOB_ADMIN_RETRY_COUNT` | `0` | Same-address synchronous retries for transient errors (capped). |
| `XXL_JOB_ADMIN_RETRY_BACKOFF` | `0.0` | Seconds to wait between retries (capped). |
| `XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR` | `True` | Try the next admin on a non-200 status. |
| `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` | `False` | Try the next admin on an invalid JSON response. |
| `XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR` | `False` | Try the next admin on a business-code failure. |
| `XXL_JOB_LOG_ENABLED` | `False` | Enable plugin-managed logging. |
| `XXL_JOB_LOG_FILE_ENABLED` | `True` | Add a rotating-file handler when managed logging is enabled. |
| `XXL_JOB_LOG_CONSOLE_ENABLED` | `True` | Add one console handler for normal and error records. |
| `XXL_JOB_LOG_LEVEL` | `"INFO"` | Shared level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `XXL_JOB_LOG_FORMAT` | `"%(asctime)s [%(levelname)s] [%(name)s] %(message)s"` | Shared standard Logging format. |
| `XXL_JOB_LOG_DATE_FORMAT` | `"%Y-%m-%d %H:%M:%S"` | Formatter date format; empty uses Logging's default. |
| `XXL_JOB_LOG_PATH` | `"./logs"` | Directory; relative paths resolve from the process working directory. |
| `XXL_JOB_LOG_FILENAME` | `"flask-xxljob.log"` | Log file name. |
| `XXL_JOB_LOG_ENCODING` | `"utf-8"` | Valid Python text encoding. |
| `XXL_JOB_LOG_MAX_BYTES` | `10485760` | Positive rotation threshold in bytes. |
| `XXL_JOB_LOG_BACKUP_COUNT` | `5` | Non-negative rotated backup count. |
| `XXL_JOB_LOG_PROPAGATE` | `False` | Propagate records while a managed target exists. |

Request size is measured in **bytes**; `handleMsg` and `executorParams` lengths
are measured in **characters** (Unicode code points), so multi-byte characters
such as Chinese count as one character each.

Network and timeout errors always fail over to the next admin regardless of the
failover keys above.

## Example

```python
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=[
        "http://admin-1:8080/xxl-job-admin",
        "http://admin-2:8080/xxl-job-admin",
    ],
    XXL_JOB_ACCESS_TOKEN="",
    XXL_JOB_EXECUTOR_APP_NAME="project-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_AUTO_REGISTER=True,
    XXL_JOB_DEREGISTER_ON_EXIT=False,
    XXL_JOB_REGISTRY_INTERVAL=30,
)
```

## Registry lifecycle

The only automatic-start condition is `XXL_JOB_ENABLED and
XXL_JOB_AUTO_REGISTER`. When true, `init_app()` installs the Runtime, five HTTP
routes and finalizer, then calls the public `start_registry(app)`. With
`AUTO_REGISTER=False`, initialization still provides the executor protocol and
the application may call `start_registry(app)` later.

`stop_registry()` is local-only by default: it wakes and detaches the current
renewal Worker without joining, accessing Admin, or changing `registered`.
`stop_registry(remove=True)` validates Registry configuration synchronously,
then requests at most one background `registryRemove` for the latest non-zero
lifecycle generation. For deterministic removal, use `stop_registry()` and
then `remove_executor()`.

Exit removal defaults to off. When explicitly enabled it is best-effort and
non-blocking; interpreter termination, `SIGKILL`, or forced container shutdown
can prevent it from completing.

## Validation

Validation has three layers. Removed keys are detected first, even when
`XXL_JOB_ENABLED=False`. Existing field type/value checks run during
`init_app()`. Full Registry completeness is checked only immediately before an
enabled `start_registry()`, `register_executor()`, `remove_executor()`, or
`stop_registry(remove=True)` operation. Consequently, an enabled protocol-only
deployment with `AUTO_REGISTER=False` may omit Admin and executor Registry
settings. When provided, admin and executor addresses must use
the `http` or `https` scheme and contain a host and valid port; context paths are
supported. Addresses are normalized on load (surrounding whitespace and
redundant trailing slashes are removed while context paths and order are
preserved). When set, `XXL_JOB_ROUTE_PREFIX` is always appended to
`XXL_JOB_EXECUTOR_ADDRESS`; do not embed the route prefix in the executor
address. A whitespace-only access token is normalized to
empty (no-token mode), while a non-empty token is preserved. Validation messages
name the offending key, its received type and the expected format. Bad
configuration is never silently ignored.

All boolean settings accept real booleans only. Levels, encodings, rotation
values and log formats are validated during initialization; the format is
exercised against a synthetic `LogRecord`, so an unknown field fails before
the application starts. If managed logging is disabled—or both output targets
are disabled—the extension does not override the runtime logger's level or
propagation, allowing the host to configure the `flask_xxljob` logger. See
[Logging](logging.md).

When `XXL_JOB_ENABLED=False`, Registry lifecycle and one-shot APIs short-circuit
before full validation, threads, Remove operations, network locks, RPCs, or RPC
sequence allocation. The synchronous one-shot APIs return a config-failure
`CallResult` with `error="Flask-XXLJob is disabled."`; they update only the
current process's safe local failure snapshot and preserve `registered`.

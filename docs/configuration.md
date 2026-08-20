[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# Configuration

All configuration is read from `app.config` during `init_app()`. The extension
never reads configuration at import time and never accesses `current_app` in
the constructor.

## Keys

| Key | Default | Description |
| --- | --- | --- |
| `XXL_JOB_ENABLED` | `True` | Master switch for routes and all Registry, Remove and Callback Admin traffic. |
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
| `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` | `False` | Try the next admin on invalid JSON or an invalid response object. |
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
XXL_JOB_AUTO_REGISTER`. When true, `init_app()` privately creates the Runtime,
starts an activation-gated Prepared Thread, prepares a detachable finalizer
handle, commits the Flask protocol resources, and then lets the Prepared creator
activate the Worker. With `AUTO_REGISTER=False`, initialization still provides
the executor protocol and the application may call `start_registry(app)` later.

`stop_registry()` is local-only by default: it wakes and detaches the current
renewal Worker without joining, accessing Admin, or changing `registered`.
`stop_registry(remove=True)` validates Registry configuration synchronously,
then requests one background `registryRemove` for the current cleanup scope.
That scope can be generation zero after an accepted manual Register, without
creating a Worker or advancing its generation. Successful terminal cleanup is
reused by later lifecycle shutdown. A subsequent accepted register can recreate
the remote identity and open a new cleanup responsibility in the same
generation. For deterministic removal, use `stop_registry()` and then
`remove_executor()`.

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
settings. When enabled, admin and executor addresses must use the `http` or
`https` scheme and contain a valid hostname/IPv4/IPv6 literal and port; context
paths are supported. Raw C0/DEL/control and whitespace characters, userinfo,
query strings and fragments are rejected before URL parsing. Only redundant
trailing slashes are normalized; surrounding whitespace is never silently
trimmed. When set, `XXL_JOB_ROUTE_PREFIX` is always appended to
`XXL_JOB_EXECUTOR_ADDRESS`; do not embed the route prefix in the executor
address. Root, an optional leading slash and one trailing slash are compatible;
whitespace/control characters, `?`, `#`, backslash, angle brackets, consecutive
slashes, Flask converters and `.`/`..` segments are rejected. A whitespace-only access token is normalized to
empty (no-token mode), while a non-empty token is preserved. Validation messages
name the offending key, its received type and the expected format. Bad
configuration is never silently ignored.

`init_app()` treats these deterministic checks as a side-effect-free preflight.
When automatic Registry startup is requested, full Registry completeness plus
executor route, Blueprint and CLI-name conflicts are checked before any managed
resource or Flask state is created. Private prepare may then create logging, an
activation-gated Thread and a detachable finalizer handle, but publishes none of
them through Flask or the application registry. A failure removes only
reversible state still owned by that initialization. The project does not edit
Flask's private route/hook structures to provide a general commit rollback.

All boolean settings accept real booleans only. Levels, encodings, rotation
values and log formats are validated during initialization; the format is
exercised against a synthetic `LogRecord`, so an unknown field fails before
the application starts. If managed logging is disabled—or both output targets
are disabled—the extension does not override the runtime logger's level or
propagation, allowing the host to configure the `flask_xxljob` logger. See
[Logging](logging.md).

When `XXL_JOB_ENABLED=False`, no executor Blueprint is registered and Registry,
Remove and Callback paths short-circuit before threads, network locks, RPCs or
sequence allocation. The synchronous APIs return a config-failure `CallResult`
with `error="Flask-XXLJob is disabled."`; lifecycle calls are no-ops. Removed
keys, local field/container types and logging configuration are still checked,
but unused URL strings and Route Prefix strings receive no network/Flask-path
semantic validation. A Callback-only process must instead use
`XXL_JOB_ENABLED=True` with `XXL_JOB_AUTO_REGISTER=False`.

All Admin POSTs use redirect-disabled requests. HTTP 3xx is handled as an HTTP
failure without replaying credentials or payloads to the target. A JSON parse
failure is `invalid_json`; a non-object body, non-integer (or boolean) `code`,
or non-string/non-`None` `msg` is `invalid_response`. The latter uses the same
failover setting as invalid JSON, and only integer `code == 200` is successful.

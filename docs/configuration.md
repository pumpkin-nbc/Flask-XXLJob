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
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | Address the admin uses to reach this executor. |
| `XXL_JOB_ROUTE_PREFIX` | `""` | URL prefix for the executor endpoints. |
| `XXL_JOB_AUTO_REGISTER` | `True` | Start automatic registration renewal. |
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
    XXL_JOB_REGISTRY_INTERVAL=30,
)
```

## Validation

Configuration is validated on `init_app()`. Invalid types raise
`XXLJobConfigError`. `XXL_JOB_EXECUTOR_APP_NAME`, at least one
`XXL_JOB_ADMIN_ADDRESSES` entry and `XXL_JOB_EXECUTOR_ADDRESS` are required only
when `XXL_JOB_AUTO_REGISTER` is enabled, so a protocol-only deployment that does
not register can omit them. When provided, admin and executor addresses must use
the `http` or `https` scheme. Admin and executor addresses are normalized on
load (surrounding whitespace and redundant trailing slashes are removed while
context paths and order are preserved). Validation messages name the offending
key, its received type and the expected format. Bad configuration is never
silently ignored.

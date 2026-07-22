[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-07-22

### Fixed

- Admin and executor addresses are normalized when configuration is loaded: surrounding whitespace and redundant trailing slashes are removed while any context path (for example `/xxl-job-admin`) and address order are preserved. This makes registry, deregistration and callback URLs consistent regardless of how the address was written.

### Changed

- The result returned by `register_executor`, `remove_executor` and the `callback*` methods now carries an optional `error_type` category (`network`, `timeout`, `http`, `invalid_json`, `business`, `config`, or `None` on success), so failures can be classified without inspecting the underlying `requests` objects. The existing `CallResult`/`AdminCallResult` fields are unchanged and the access token is still never included in any result.
- Configuration validation error messages now consistently include the configuration key, the received value type (or value for non-sensitive fields), and the expected format.

### Testing

- Added tests for call-result error classification (registration and callback: network, timeout, HTTP, invalid JSON, business failure, and no-admin), admin/executor address normalization, route-prefix variants (empty, leading/trailing/duplicate slashes), and `Content-Type: application/json; charset=UTF-8` parsing including Chinese `executorParams`.

### Documentation

- Added a "0.1.1 to 0.1.2" upgrade and rollback guide, refreshed the bilingual docs and version references, and recorded the `error_type` result field.

Upgrade note: this is a backward-compatible patch release. Upgrade with:

```bash
pip install --upgrade Flask-XXLJob==0.1.2
```

No code or configuration changes are required; the only addition is the optional `error_type` field on call results.

## [0.1.1] - 2026-07-22

### Fixed

- Module-level callback registration before `init_app` (the `@xxl_job.on_run` decorator applied at import time) now works instead of raising when no application context exists.
- `_resolve_app` uses `flask.has_app_context()` so callback and registration helpers no longer raise a confusing `RuntimeError` outside an application context.
- Executor endpoints always return XXL-JOB standard JSON. Empty bodies, non-JSON payloads and JSON arrays/scalars now produce a clear `code: 500` failure instead of being silently treated as `{}`.
- Numeric fields (`jobId`, `logId`, `logDateTime`, and so on) are coerced safely: a missing value uses the default, `0` is preserved, and a non-numeric value returns a protocol failure rather than crashing.
- Wrong HTTP methods (405) on executor routes return XXL-JOB JSON instead of a Werkzeug HTML error page; other application routes keep Flask's default behavior.
- Task-result callbacks stop on the first valid admin business response, avoiding duplicate delivery across multiple admin addresses.

### Changed

- Duplicate callback registration now raises `XXLJobError` instead of silently overwriting the previous handler.
- Handler return values other than `XXLJobResponse` (and `LogResponse` for `/log`) return an explicit "unsupported response type" failure.
- Configuration validation requires admin addresses, executor name and executor address only when `XXL_JOB_AUTO_REGISTER` is enabled, and validates that admin/executor addresses use the `http`/`https` scheme.
- `callback`, `callback_success` and `callback_failure` accept `message=None` and validate that `log_id`/`log_date_time` are integers (booleans are rejected). Existing `handle_msg` keyword usage remains compatible.
- Added exception types `XXLJobConfigurationError`, `XXLJobRequestError`, `XXLJobProtocolError`, `XXLJobRegistryError` and the `AdminCallResult` alias with `message`/`admin_address` accessors. `XXLJobConfigError` remains as an alias.

### Documentation

- Refreshed the bilingual README and `docs/` pages to describe pre-init registration, duplicate-registration behavior, unified JSON error responses, relaxed configuration rules and the extended result/exception model.

### Testing

- Added regression and protocol tests for registration patterns, request parsing, handler return types, unified error responses, configuration validation, URL joining, callback validation and multi-admin failover semantics.

Upgrade note: this is a backward-compatible patch release. Upgrade with:

```bash
pip install --upgrade Flask-XXLJob==0.1.1
```

The only behavior change to be aware of is that registering the same callback twice now raises `XXLJobError` instead of silently overwriting the earlier handler.

## [0.1.0] - 2026-07-21

### Added

- Flask extension implementing the official XXL-JOB 2.4.1 executor protocol.
- Application Factory support with per-application runtime isolation stored in `app.extensions["xxljob"]`.
- Executor endpoints: `/beat`, `/idleBeat`, `/run`, `/kill`, `/log`.
- Request-callback registration: `on_run`, `on_idle_beat`, `on_kill`, `on_log`.
- Access token validation using the official `XXL-JOB-ACCESS-TOKEN` header.
- Executor registration, deregistration and automatic renewal.
- Task-result callback client: `callback`, `callback_success`, `callback_failure`.
- Multiple admin addresses with failover.
- Flask CLI group `xxljob` and standalone `flask-xxljob` console script.
- Bilingual (English and Simplified Chinese) documentation.

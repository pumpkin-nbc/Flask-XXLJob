[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.4] - 2026-07-25

### Changed

- Automatic registration during `init_app()` now depends only on
  `XXL_JOB_ENABLED` and `XXL_JOB_AUTO_REGISTER`. It no longer checks
  `app.debug` or `WERKZEUG_RUN_MAIN`, so Gunicorn (and similar) with
  `DEBUG=True` still starts the registry thread.

## [0.3.3] - 2026-07-24

### Added

- `XXLJobResponse.success()` now accepts an optional `msg` as its first
  argument, mapping to the official `ReturnT.msg` field. `content` remains the
  second argument; the default `msg` remains `None`.

### Documentation

- Documented long-running / Celery callback flow, Admin job timeout for
  “任务结果丢失，标记失败”, and that callback outbox / durable retry remain
  outside the plugin’s scope.

## [0.3.2] - 2026-07-23

### Changed

- `XXL_JOB_EXECUTOR_ADDRESS` is now treated as the service base URL only.
  `XXL_JOB_ROUTE_PREFIX` is always appended when the configuration is loaded,
  so Admin registers against the same path the executor endpoints use.

## [0.3.1] - 2026-07-23

### Changed

- Changed the distribution metadata name to its normalized lowercase spelling,
  `flask-xxljob`. This remains the same PyPI project as `Flask-XXLJob`; the
  Python import package remains `flask_xxljob`.
- Updated the Trusted Publishing workflow and release documentation to publish
  `v0.3.1` after the TestPyPI `0.3.0` release.

## [0.3.0] - 2026-07-23

### Added

- Added optional, per-application Flask-XXLJob managed logging using only the
  standard library. Managed logging is disabled by default; rotating-file and
  console targets can be enabled independently or together.
- Console logging is enabled whenever managed logging is enabled by default,
  and one console handler emits both normal and error records. Added shared
  level and format validation, sensitive-data filtering, lifecycle cleanup,
  and logging fields in `XXLJobStatus` and `xxljob status`.
- Managed console records are colorized by level: blue `DEBUG`, green `INFO`,
  yellow `WARNING`, red `ERROR`, and bold red `CRITICAL`. File logs remain
  free of ANSI escape sequences.

### Changed

- `/run` now dispatches by exact, case-sensitive `executorHandler` through
  `@xxl_job.on_run("name")`. Multiple named handlers are supported; the bare
  decorator and unnamed fallback were removed. Application-level Run APIs now
  use `set_run_callback(app, name, func)`, `get_run_callback(app, name)` and
  mapping-style `register_callbacks(run={name: func})`, with atomic validation.
- Application resolution is no longer ambiguous outside a Flask application context: omitting `app` remains valid with exactly one initialized application, while an extension shared by multiple initialized applications now requires an explicit `app`. Pre-initialization `on_*` decorators continue to seed every subsequently initialized app.
- Package metadata, `flask_xxljob.__version__` and the CLI now use `flask_xxljob/_version.py` as their single version source.
- Route-conflict checks, application resolution and lifecycle coordination were split into internal helpers without changing public import paths.

### Documentation

- Updated the bilingual README, API reference and migration guide for strict string validation, route-conflict detection, delayed deregistration and the multi-application migration.
- Added bilingual logging and deployment guidance, including a console-only
  container setup and the multi-process limitation of `RotatingFileHandler`.
- Added a bilingual, tested end-to-end Flask integration example covering Application Factory setup, all executor callbacks, environment configuration and final task-result reporting.
- Reworked the primary quick start into a beginner-first, locally runnable path with a tested single-file example, PowerShell/Bash requests, Admin onboarding and troubleshooting.

## [0.2.1] - 2026-07-22

### Fixed

- Trigger, callback and registry string fields now accept only strings; missing values and `None` still use the documented defaults. Invalid executor requests return an XXL-JOB `code=500` response, while invalid outgoing callbacks raise `XXLJobValidationError` before any HTTP request is sent.
- Initialization now rejects conflicting executor `POST` paths before registering CLI commands, blueprints, extension state or registry threads. Same-path `GET` routes remain valid.
- When registry shutdown times out behind an in-flight renewal, the worker performs the requested deregistration after renewal completes, serially and at most once.
- Whitespace-only access tokens are normalized to empty, and Admin/executor URLs are validated with standard URL parsing for an `http`/`https` scheme, host and valid port while preserving context paths.

### Testing

- Added strict model-validation, route-conflict and delayed-deregistration regressions. CI now enforces at least 90% coverage on Python 3.12/Flask 3 and validates documentation, wheel/sdist contents, metadata and an installed-wheel CLI smoke test.

## [0.2.0] - 2026-07-22

### Fixed

- Non-object JSON responses from the Admin are now classified as `invalid_json` instead of raising `AttributeError`.
- Executor request bodies are read with a strict memory bound, `/` is normalized to the root route prefix, and executor routing errors no longer replace the host application's custom 404/405 handlers.
- Executor routes use the Flask 1.x-compatible `route(..., methods=["POST"])` API instead of the Flask 2.0-only `post()` shortcut.
- Registry shutdown no longer deregisters while an in-flight renewal may still complete and register the executor again.

### Added

- Application-level callback registration: `register_callbacks(app=None, *, run=..., idle_beat=..., kill=..., log=..., replace=False)`, `set_run_callback`/`set_idle_beat_callback`/`set_kill_callback`/`set_log_callback` (with `replace`), and `get_run_callback`/`get_idle_beat_callback`/`get_kill_callback`/`get_log_callback`. The `on_*` decorators keep working as the default template. Resolution priority is app-specific registry first, then extension-level defaults.
- Batch callback: `callback_many(callbacks, app=None)` sends multiple `HandleCallbackParam` entries in a single official request. Every item is validated before sending, the batch is never auto-split, and an invalid item or exceeding `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` rejects the whole batch without sending anything.
- Configurable, bounded synchronous Admin call policy: `XXL_JOB_ADMIN_RETRY_COUNT`, `XXL_JOB_ADMIN_RETRY_BACKOFF`, `XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR`, `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON`, `XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR`. Retry and backoff are capped; no background threads or persistence are introduced.
- `CallResult`/`AdminCallResult` gained additive fields `attempt_count`, `elapsed_ms` and `http_status` (all defaulted).
- Plugin status querying: the `XXLJobStatus` model plus `get_status(app=None)`, and registry lifecycle control via `start_registry(app=None)` / `stop_registry(app=None)`. Status describes only the plugin (never the token or any business-task state).
- CLI `xxljob status` command (Flask group and standalone) with human-readable, token-free output and a non-zero exit code when the last registration failed.
- Public exception hierarchy rooted at `FlaskXXLJobError` with `XXLJobInitializationError`, `XXLJobCallbackRegistrationError`, `XXLJobValidationError`, `XXLJobAdminCallError` (and existing subclasses). All previous names remain as aliases (`XXLJobError`, `XXLJobConfigError`, `XXLJobRequestError`, ...).
- New `docs/api-reference` and `docs/integration-testing` pages, a `tox.ini` and GitHub Actions matrix, opt-in official XXL-JOB 2.4.1 integration tests (gated by `XXLJOB_ADMIN_URL`), and three new examples: `batch_callback`, `multiple_apps`, `registry_status`.

### Changed

- The project license changed from MIT to Apache-2.0 before the first PyPI release. Package metadata now identifies Pumpkin as the author and points to the `pumpkin-nbc/Flask-XXLJob` repository.
- Access-token comparison now uses `hmac.compare_digest` for constant-time behaviour and safely rejects missing/non-string headers. The empty-token official mode is unchanged; the token is never logged or returned.
- When an explicit Admin call policy is supplied (as the built-in clients now do), the default failover behaviour is: network/timeout always fail over; HTTP errors fail over; invalid-JSON and business failures do not fail over. Direct `post_to_admins` callers without a policy keep exact 0.1.2 behaviour.

### Security

- Constant-time access-token comparison reduces timing side channels. Request body size (bytes) and `executorParams` length (characters) limits still return XXL-JOB JSON errors, never HTML.

### Testing

- Added tests for app-level registration (priority, multi-app isolation, duplicate/`replace`, factory seeding, handler exception/bad return), batch callback (empty/over-limit/invalid item/Chinese/truncation/failover/no-partial-send), retry policy (retry, exhaustion, failover, caps, token absence, new fields), status/lifecycle and CLI status, and access-token/request-limit security.
- Added regressions for non-object Admin JSON, bounded request-stream reads, host error-handler preservation, root-prefix normalization and slow registry shutdown; package checks now validate license metadata and legal files. The Flask 1.x test environments pin a compatible MarkupSafe version.

### Documentation

- Added a "0.1.2 to 0.2.0" migration section, the API reference and integration-testing guides, a compatibility matrix note, and refreshed the bilingual configuration/callback/request-callbacks docs and README.

Upgrade note: this is a backward-compatible minor release. Upgrade with:

```bash
pip install --upgrade flask-xxljob==0.2.0
```

No code or configuration changes are required. All new behaviour is opt-in via new APIs and config keys whose defaults match 0.1.2.

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
pip install --upgrade flask-xxljob==0.1.2
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
pip install --upgrade flask-xxljob==0.1.1
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

[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-08-16

### Changed

- Consolidated PID isolation, lifecycle generations, current/stopping Worker
  ownership, Pending/Active Remove, cleanup scheduling, RPC ordering and final
  log closure in `RegistryService`.
- Automatic startup still has one condition (`XXL_JOB_ENABLED &&
  XXL_JOB_AUTO_REGISTER`), but now starts an activation-gated Prepared Thread
  before Flask commit. Only its creating call may commit the generation/Worker
  and wake it after commit; the Prepared stage performs no Admin RPC.
- Runtime finalizer creation is also prepared before Flask commit as a private,
  detachable handle. It publishes no Flask/application-registry state, and a
  failed initialization detaches it without invoking Runtime shutdown or Admin.
- `stop_registry(remove=False)` is now the default: it detaches and wakes local
  renewal immediately without joining, contacting Admin, or changing the
  latest `registered` snapshot. `remove=True` schedules one background Remove
  for the current cleanup responsibility.
- All real Registry RPCs in one process share one network lock. Completions use
  strictly increasing sequences so a late older success or failure cannot
  overwrite newer accepted state.
- PID changes replace only blank process-specific Registry state before any
  inherited Lock, Thread, or Event is touched; application Runtime, handlers,
  callbacks, routes, configuration and the resource-free AdminClient remain.
- Runtime finalization is non-blocking. Exit removal is best-effort, uses the
  same generation eligibility and scheduler, and managed logs close once after
  all background cleanup is idle.
- Terminal Remove is now idempotent by generation cleanup responsibility.
  Successful synchronous, Worker or cleanup-actor removal is reused by later
  lifecycle shutdown. An accepted same-generation register reopens a new
  responsibility, with one Active and at most one Pending fallback resolving
  the real RPC order without retrying failed removals.
- Active Remove completion acceptance remains based only on strict sequence,
  ProcessState identity and Active identity. Exact generation and current
  Worker state are checked separately when recording cleanup satisfaction, so
  a new generation still waits for and correctly orders behind an older Active
  Remove.
- Explicit one-shot Register calls now join the current generation's
  open coordination window before waiting for the Registry network lock.
  Lifecycle cleanup closes that window without blocking and defers Remove until
  all earlier participants finish. Register RPC completion remains ordered only
  by strict sequence and ProcessState identity; generation and Coordination
  ownership separately guard cleanup-responsibility changes.
- Generation zero is now a manual cleanup scope. An accepted explicit Register
  creates exit-cleanup responsibility without creating a Worker, advancing the
  Worker generation or starting renewal. Successful/failed explicit Remove and
  shutdown reuse the existing Active/Pending ownership, while generation-zero
  cache never satisfies generation one.
- `init_app()` now completes a side-effect-free deterministic preflight,
  including route, Blueprint and CLI-name conflicts, before creating managed
  resources. Commit failures remove only CLI, extension and application records
  still owned by that initialization; Flask private route/hook structures are
  not treated as a general rollback surface.
- Protocol routes and the routing-error hook are constructed on an unregistered
  Blueprint. Reversible CLI, extension, application-registry and finalizer
  ownership is published first; Blueprint registration is the final irreversible
  commit before Prepared creator activation. Once the exact Blueprint object
  from this initialization is accepted by the app, later activation failures
  preserve its Runtime and lifecycle ownership instead of leaving live routes
  without extension state.
- A Prepared `Thread.start()` failure now leaves Flask uncommitted, closes the
  initialization's private managed handlers/resources, preserves the original
  error and permits retry on the same app/extension instance. Creator-only
  activation and identity-safe cancellation prevent a concurrent start or
  stale cancel from taking over or stopping a committed Worker. Any Worker
  committed before a stop still crosses the formal `try/finally` cleanup
  boundary even when it sends zero Registry RPCs.
- Flask and standalone CLI `remove` commands now stop local renewal before the
  synchronous Remove. The Worker stays stopped even when Admin removal fails;
  the low-level `remove_executor()` behavior is unchanged.
- User callback and unexpected internal exceptions retain full local
  tracebacks, while expected network/HTTP/remote failures remain concise
  `CallResult` events and protocol responses remain generic.
- All four public Callback forms now resolve their target Runtime before the
  disabled check, then return one shared disabled `CallResult` before payload
  construction, validation or iteration. Application-resolution errors and all
  enabled payload validation/conversion behavior remain unchanged.
- The build backend remains capped below Hatchling 1.32 so current Twine can
  validate Core Metadata 2.4 artifacts.
- Admin/executor URLs now reject raw C0/DEL/whitespace, userinfo, query,
  fragment and invalid host/port input; static Route Prefix validation rejects
  converters, dot segments, percent encoding and ambiguous URL syntax. Admin
  POST never follows redirects. Invalid JSON structure is classified separately as
  `invalid_response` (exported from `flask_xxljob.client`) and reuses the
  invalid-JSON failover option.

### Configuration

- Removed the unreleased `XXL_JOB_AUTO_REGISTER_ON_INIT` key. Its presence is a
  synchronous migration error, including when the extension is disabled.
- Changed `XXL_JOB_DEREGISTER_ON_EXIT` to default to `False` so one worker does
  not automatically remove a shared executor identity.
- Split initialization field validation from full Registry completeness.
  `AUTO_REGISTER=False` can initialize the HTTP protocol without Admin Registry
  settings; enabled Registry operations validate before threads or RPCs.
- `XXL_JOB_ENABLED=False` is the complete feature switch: no executor Blueprint
  is registered and Registry, Remove and Callback paths perform no Admin HTTP.
  Local Runtime/status/CLI and basic type/log validation remain; unused network
  URL and Route Prefix strings are not semantically interpreted. Callback-only
  processes use `ENABLED=True`, `AUTO_REGISTER=False`.

### Compatibility

- When enabled, the task protocol, Handler and Callback APIs, five executor endpoints, Admin
  Registry protocol, renewal interval, `XXLJobStatus` fields, public imports,
  Python 3.8-3.14 and Flask 1.x-3.x support remain unchanged.
- Multi-worker topology remains process-per-Registry-Worker. No leader election,
  cross-process lock, signal handler, or deployment detection was added.

### Testing

- Release checks now build into a clean temporary directory, validate the one
  new wheel and sdist (including file-only RECORD mappings and authoritative
  top-level PKG-INFO), reject development/signature files, and run a
  source-isolated installed-wheel smoke test with `pip check`.
- The final local suite completed with 632 passed, 2 optional official-Admin
  tests skipped, and 92.22% line coverage. It covers the total disabled switch,
  strict URLs/Admin responses, generation-zero cleanup and transitions,
  PID/generation ownership, Remove races, strict completion sequences, Prepared
  ownership, identity-safe pre-commit cleanup and one-time log closure.

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

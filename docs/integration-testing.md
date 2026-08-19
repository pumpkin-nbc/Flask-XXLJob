[English](integration-testing.md) | [简体中文](integration-testing.zh-CN.md)

# Integration testing against XXL-JOB 2.4.1

The unit and integration test suite runs fully offline with mocked HTTP calls.
This document describes the **opt-in** integration tests that talk to a real
XXL-JOB 2.4.1 admin, plus the manual, repeatable verification steps.

These tests are **skipped by default**. They require network access and a
running admin, so they are not executed in CI automatically. No result is
claimed as passing unless it was actually run.

## Automated opt-in tests

`tests/integration/test_official_admin.py` runs only when `XXLJOB_ADMIN_URL` is
set. It registers the executor, checks the status, and removes it.

```bash
# Windows PowerShell
$env:XXLJOB_ADMIN_URL = "http://127.0.0.1:8080/xxl-job-admin"
$env:XXLJOB_ACCESS_TOKEN = "default_token"        # optional
$env:XXLJOB_EXECUTOR_ADDRESS = "http://127.0.0.1:5001"  # optional
.venv\Scripts\python.exe -m pytest tests/integration/test_official_admin.py -q
```

Supported environment variables:

- `XXLJOB_ADMIN_URL` (required): one or more admin base URLs, comma-separated.
- `XXLJOB_ACCESS_TOKEN` (optional): access token; omit for no-token mode.
- `XXLJOB_EXECUTOR_ADDRESS` (optional): the executor address the admin calls back.
- `XXLJOB_APP_NAME` (optional): the executor app name.

## Manual verification checklist

Perform these against a live XXL-JOB 2.4.1 admin to fully verify protocol
compatibility:

1. **Registration / renewal / removal**: start the app with
   `XXL_JOB_AUTO_REGISTER=True`; confirm the executor appears online in the
   admin and keeps renewing. For deterministic removal, call
   `stop_registry(remove=False)` followed by `remove_executor()`, then confirm
   that it disappears. Normal shutdown does not remove it because
   `XXL_JOB_DEREGISTER_ON_EXIT=False` is the default.
2. **All five endpoints**: trigger `/run`, `/idleBeat`, `/kill`, `/log`, and
   confirm `/beat` health via the admin.
3. **Single and batch callback**: use `callback` / `callback_success` /
   `callback_failure` and `callback_many`; confirm the log status updates.
4. **Access token on and off**: verify a correct token passes, a wrong token is
   rejected, and no-token mode works when the admin has no token configured.
5. **Route prefix**: set `XXL_JOB_ROUTE_PREFIX` (keep `XXL_JOB_EXECUTOR_ADDRESS`
   as the base URL) and confirm the admin reaches the prefixed endpoints.
6. **Chinese executor params**: dispatch a job with Chinese `executorParams` and
   confirm correct decoding.
7. **Multiple admin addresses**: configure two admins and confirm failover for
   registration and callbacks.

## Locally verified matrix (honest report)

Only the following was actually executed in this environment on 2026-08-17:

- Python 3.12.13 with Flask 3.1.3 in the project `.venv`: 503 offline tests
  passing, 2 live-Admin tests skipped by environment, and 93.27% coverage.
- `pip check`, Ruff, mypy, bilingual documentation checks, wheel/sdist checks,
  and clean installed-wheel smoke tests passing.

The remaining Python/Flask combinations are **configured in CI**
(`.github/workflows/ci.yml`), but were **not executed locally**.
The official XXL-JOB 2.4.1 integration tests above were **not executed** here
because no live admin was available; the two skipped tests are those opt-in
checks.

[English](README.md) | [简体中文](README.zh-CN.md)

# Complete Flask integration

This example is a production-shaped Flask Application Factory integration. It
covers executor configuration, all five XXL-JOB executor endpoints, task
submission, cancellation, log paging, and the final task-result callback.

Flask-XXLJob is only the protocol adapter. `TaskGateway` is deliberately a
stub: replace it with your Celery, message queue, RPC, or existing task-service
client. The example does not create an execution pool or run business jobs in
the `/run` request.

## Request flow

```text
XXL-JOB Admin
    -> POST /xxl-job/run
    -> Flask-XXLJob validates and parses TriggerParam
    -> exact JobHandler selects handle_demo or handle_report
    -> the selected callback submits the full TriggerRequest to your task service
    -> task service completes asynchronously
    -> POST /internal/task-result to this Flask app
    -> callback_success/callback_failure
    -> XXL-JOB Admin /api/callback
```

The task service must retain `logId` and `logDateTime` from the trigger and send
them back unchanged with the final result.

## Install and run

From the repository root:

```bash
python -m pip install -e .
```

PowerShell:

```powershell
$env:XXL_JOB_ACCESS_TOKEN = "replace-with-admin-token"
$env:INTERNAL_RESULT_TOKEN = "replace-with-internal-token"
$env:XXL_JOB_AUTO_REGISTER = "false"
flask --app "examples.complete_integration.app:create_app" run --host 0.0.0.0 --port 5001
```

Bash:

```bash
export XXL_JOB_ACCESS_TOKEN="replace-with-admin-token"
export INTERNAL_RESULT_TOKEN="replace-with-internal-token"
export XXL_JOB_AUTO_REGISTER=false
flask --app 'examples.complete_integration.app:create_app' run --host 0.0.0.0 --port 5001
```

Use a production WSGI server instead of Flask's development server in a real
deployment.

## Environment variables

| Variable | Example/default | Purpose |
| --- | --- | --- |
| `XXL_JOB_ADMIN_ADDRESSES` | `http://127.0.0.1:8080/xxl-job-admin` | Comma-separated Admin base URLs. |
| `XXL_JOB_ACCESS_TOKEN` | empty | Must match the Admin access token. |
| `XXL_JOB_EXECUTOR_APP_NAME` | `complete-flask-executor` | Executor AppName configured in XXL-JOB. |
| `XXL_JOB_EXECUTOR_ADDRESS` | `http://127.0.0.1:5001` | Base URL Admin uses to reach the executor. `XXL_JOB_ROUTE_PREFIX` is appended automatically. |
| `XXL_JOB_ROUTE_PREFIX` | `/xxl-job` | Mount point for `/beat`, `/run`, `/idleBeat`, `/kill`, and `/log`. |
| `XXL_JOB_AUTO_REGISTER` | `false` | Set to `true` after Admin and the public executor address are reachable. |
| `INTERNAL_RESULT_TOKEN` | empty | Required `X-Internal-Token` for the internal result endpoint. |

When `XXL_JOB_ROUTE_PREFIX` changes, you do not need to rewrite
`XXL_JOB_EXECUTOR_ADDRESS`; the prefix is appended on load.

## Configure XXL-JOB Admin

1. Create or select an executor with AppName `complete-flask-executor`.
2. Use automatic registration by setting `XXL_JOB_AUTO_REGISTER=true`, or set
   its manual address to `http://<flask-host>:5001/xxl-job`.
3. Configure the Admin access token and set the same value in
   `XXL_JOB_ACCESS_TOKEN`.
4. Create BEAN jobs whose JobHandler is exactly `demoJobHandler` or
   `reportJobHandler`. Those names match the two `@xxl_job.on_run("name")`
   decorators; matching is automatic and case-sensitive.
5. Put plain text or JSON in Executor Parameters. Call
   `trigger.parse_params()` to receive parsed JSON when applicable.

## Local protocol checks

Health check:

```bash
curl http://127.0.0.1:5001/healthz
```

Executor heartbeat:

```bash
curl -X POST http://127.0.0.1:5001/xxl-job/beat \
  -H 'XXL-JOB-ACCESS-TOKEN: replace-with-admin-token' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Trigger a task manually:

```bash
curl -X POST http://127.0.0.1:5001/xxl-job/run \
  -H 'XXL-JOB-ACCESS-TOKEN: replace-with-admin-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "jobId": 1,
    "executorHandler": "demoJobHandler",
    "executorParams": "{\"customerId\": 42}",
    "logId": 10001,
    "logDateTime": 1784736000000
  }'
```

Change `executorHandler` to `reportJobHandler` to select the second callback.
An unknown name is not passed to either callback and returns:

```json
{"code":500,"msg":"Unsupported JobHandler: unknownJobHandler","content":null}
```

Simulate the business task service reporting completion:

```bash
curl -X POST http://127.0.0.1:5001/internal/task-result \
  -H 'X-Internal-Token: replace-with-internal-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "logId": 10001,
    "logDateTime": 1784736000000,
    "success": true,
    "message": "completed"
  }'
```

The final call requires a reachable XXL-JOB Admin. If Admin is unavailable, the
internal endpoint returns HTTP 502 with the classified callback error.

## Production adaptation checklist

- Replace every `TaskGateway` method with calls to the real task and log services.
- Persist or reliably deliver final results in your business system when losing
  a callback is unacceptable; Flask-XXLJob intentionally has no callback outbox.
- Keep `/internal/task-result` on a private network and replace the sample token
  with your service-authentication mechanism if available.
- Use HTTPS and configure connect/read timeouts and bounded retry policy.
- Set the executor address to the externally reachable reverse-proxy URL.
- Pass `app=` to callback helpers outside an application context, especially
  when one `FlaskXXLJob` instance initializes multiple applications.

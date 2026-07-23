[English](getting-started.md) | [简体中文](getting-started.zh-CN.md)

# Beginner's Guide: Your First Flask Executor

This guide assumes that you know basic Python but have not used Flask or
XXL-JOB before. Follow it in order: first make the example work locally, then
connect it to XXL-JOB Admin.

## 1. Understand the three parts

- **XXL-JOB Admin** schedules a job and sends an HTTP request.
- **Flask-XXLJob** translates that request into a normal Python function call.
- **Your function** submits or performs the business work and returns a protocol response.

Flask-XXLJob does not create a task queue or execute background jobs for you.
The beginner example only prints the request so that the data flow is visible.

## 2. Check Python and install

Python 3.8 or newer is required:

```bash
python --version
python -m pip install flask-xxljob
```

For a new project, using a virtual environment is recommended:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install flask-xxljob
```

The repository already contains a copy-and-run file at
[`examples/beginner/app.py`](../examples/beginner/app.py).

## 3. Run locally without XXL-JOB Admin

The beginner file deliberately uses `XXL_JOB_AUTO_REGISTER=False`. This lets
you verify Flask and the executor endpoints without installing Admin first.

PowerShell:

```powershell
python examples\beginner\app.py
```

macOS/Linux:

```bash
python examples/beginner/app.py
```

Open <http://127.0.0.1:5001/>. A JSON response means Flask is running.

## 4. Send your first test task

PowerShell:

```powershell
$body = @{
    jobId = 1
    executorHandler = "demoJobHandler"
    executorParams = '{"name":"beginner"}'
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:5001/xxl-job/run" `
    -ContentType "application/json" `
    -Body $body
```

macOS/Linux:

```bash
curl -X POST http://127.0.0.1:5001/xxl-job/run \
  -H 'Content-Type: application/json' \
  -d '{"jobId":1,"executorHandler":"demoJobHandler","executorParams":"{\"name\":\"beginner\"}"}'
```

You should receive `code: 200`, and the terminal should print the job ID,
handler and parsed parameters. At this point the package is working; no Admin
connection is involved yet.

## 5. What the example code means

- `Flask(__name__)` creates the web application.
- `FlaskXXLJob(app)` adds the five executor HTTP endpoints.
- `XXL_JOB_ROUTE_PREFIX="/xxl-job"` mounts them below `/xxl-job`.
- `@xxl_job.on_run("demoJobHandler")` binds that exact JobHandler to the function.
- `request.parse_params()` converts JSON parameters into a Python object.
- `XXLJobResponse.success()` tells Admin that the trigger was accepted.

Returning success means “the trigger was accepted”; it is not necessarily the
final business result.

## 6. Connect to XXL-JOB Admin

After the local test passes, replace the local-only configuration in `app.py`:

```python
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
    XXL_JOB_ACCESS_TOKEN="",  # Use the same token as Admin.
    XXL_JOB_EXECUTOR_APP_NAME="beginner-flask-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
    XXL_JOB_AUTO_REGISTER=True,
)
```

Then:

1. Start XXL-JOB Admin.
2. Create an executor with AppName `beginner-flask-executor`.
3. Make sure Admin can reach `XXL_JOB_EXECUTOR_ADDRESS`. In Docker or on another
   machine, `127.0.0.1` is usually wrong; use the Flask machine's reachable IP.
4. Restart Flask and check the Admin executor registry.
5. Create a BEAN job and set JobHandler to exactly `demoJobHandler`. It must
   match the decorator string, including capitalization. Flask-XXLJob rejects
   unknown names before your function is called.

If Admin has an access token, set the identical value in Flask and include it
in manual test requests with the `XXL-JOB-ACCESS-TOKEN` header.

## 7. Report the final task result

For a real asynchronous task, keep `log_id` and `log_date_time` from the trigger.
When your worker finishes, call:

```python
xxl_job.callback_success(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    message="completed",
)

# On failure, use callback_failure(...) instead.
```

The [complete integration example](../examples/complete_integration/README.md)
shows a task service reporting its result back through a protected Flask endpoint.

## Common problems

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Flask cannot start | Auto-registration is enabled but addresses are missing | Keep `XXL_JOB_AUTO_REGISTER=False` during the local stage. |
| `/run` returns 404 | Wrong route prefix | Use `/xxl-job/run` for the beginner example. |
| `/run` says `Unsupported JobHandler` | Admin name does not exactly match the decorator | Use the same case-sensitive name, such as `demoJobHandler`, in both places. |
| Response says access token is wrong | Flask and Admin tokens differ | Configure the same token on both sides. |
| Admin cannot discover the executor | Address is unreachable from Admin | Do not use `127.0.0.1` across containers or machines. |
| `/run` succeeds but no task runs | The example only prints/submits | Replace `handle_run` with your business-task submission. |
| Final status is missing | Trigger success is not the final callback | Call `callback_success` or `callback_failure` after completion. |

Next, read the [configuration reference](configuration.md) only for settings you
actually need. You do not need to understand every option before starting.

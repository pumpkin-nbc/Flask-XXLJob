[English](deployment.md) | [简体中文](deployment.zh-CN.md)

# Deployment

## Two independent paths

When the extension is enabled, initializing the HTTP executor protocol does not
require a running Registry lifecycle. Disabling the extension also disables its
five HTTP routes.

```mermaid
flowchart TD
    A["init_app()"] --> B["Preflight: configuration and Flask conflicts"]
    B -->|"Failure"| C["Return without committing XXL-JOB resources"]
    B -->|"Success"| D["Commit Runtime, logging, CLI, hooks and finalizer"]
    D --> E{"ENABLED?"}
    E -->|"Yes"| F["Register beat / idleBeat / run / kill / log"]
    F --> G["HTTP executor protocol is available"]
    E -->|"No"| H["Keep the extension disabled; do not register its routes"]
```

Registry is a separate, process-local path:

```mermaid
flowchart TD
    A["init_app()"] --> B{"ENABLED?"}
    B -->|"No"| C["Registry APIs stay disabled"]
    B -->|"Yes"| D{"AUTO_REGISTER?"}
    D -->|"Yes"| E["Public start_registry(app)"]
    D -->|"No"| F["Wait for an explicit start_registry(app)"]
    F --> E
    E --> G["Validate complete Registry configuration"]
    G --> H["PID guard and current ProcessState"]
    H --> I["Prepare candidate generation and Worker"]
    I --> J["Thread.start()"]
    J --> K["Commit generation and Worker ownership"]
    K --> L["Return immediately"]
    K --> M["Worker: registry immediately"]
    M --> N["stop_event.wait(REGISTRY_INTERVAL)"]
    N -->|"Interval elapsed"| M
    N -->|"Stop event set"| O["stop_registry(): detach, wake and return"]
```

The five executor endpoints, Handler dispatch, task execution and Callback API
are unchanged. Registry still registers immediately and then renews every
`REGISTRY_INTERVAL`.

## Lifecycle shutdown

`stop_registry()` is a local, non-blocking stop. It does not join, contact
Admin, or change the latest `registered` snapshot. A later
`stop_registry(remove=True)` may still request that generation's outstanding
cleanup responsibility, even after its Worker has exited.

`stop_registry(remove=True)` schedules the removal in the background. A Pending
Remove can be cancelled by a newer successful start; an Active Remove completes
first while the new Worker waits in the background. All Registry RPCs in one
process—renewal, background removal, `register_executor()` and
`remove_executor()`—share one network lock and never overlap.

Terminal cleanup is generation-aware but responsibility-based. One successful
terminal Active Remove is cached and reused by later shutdown or synchronous
terminal removal. If a register completion is accepted afterward in the same
generation, the remote identity exists again and a new cleanup responsibility
is opened. Registers that joined the coordination window before lifecycle
cleanup linearized are reconciled with the current Active and at most one
Pending fallback:

```mermaid
flowchart TD
    A["Terminal Remove succeeds"] --> B["Cleanup responsibility satisfied"]
    B --> C{"Accepted register in the coordinated window?"}
    C -->|"No"| D["Later lifecycle cleanup reuses success"]
    C -->|"Yes"| E["Cleanup responsibility required again"]
    E --> F{"RPC order"}
    F -->|"register then Active Remove"| G["Active satisfies cleanup; cancel Pending"]
    F -->|"Active Remove then register"| H["Keep Pending fallback"]
    H --> I["Pending performs the necessary newer Remove"]
```

An Active Remove completion is accepted by strict sequence, ProcessState
identity and Active identity. Exact generation and the absence of a current
Worker are checked separately only when recording that cleanup responsibility
as satisfied. This preserves the existing old-Active/new-generation order: the
new Worker waits for the old Active completion, rechecks ownership, then
registers.

For deterministic removal and its `CallResult`, use:

```python
xxl_job.stop_registry(app)
result = xxl_job.remove_executor(app)
```

Do not combine this with `stop_registry(remove=True)` for the same intended
removal.

The Flask and standalone CLI `remove` commands are terminal management
operations. They stop local renewal first and then perform the synchronous
Remove above. A failed Admin Remove returns a non-zero exit code, but the local
Worker stays stopped and does not register again. This does not change the
low-level `remove_executor()` API.

## Executor address

Set `XXL_JOB_EXECUTOR_ADDRESS` to a URL the Admin can reach. In containers or
multi-host deployments this is normally a service address, not `127.0.0.1`.
Set only the base URL; `XXL_JOB_ROUTE_PREFIX` is appended automatically.

## Gunicorn preload and fork safety

Use explicit Registry startup when the application can be imported before
forking:

```python
app.config["XXL_JOB_AUTO_REGISTER"] = False
xxl_job.init_app(app)

# Run only in a worker/process that should own Registry renewal.
xxl_job.start_registry(app)
```

Every local state access performs a PID guard first. A child replaces the
entire Registry ProcessState without acquiring a parent Lock, inspecting a
parent Worker, joining a parent Thread, or setting a parent Event. The Runtime,
handlers, callbacks, routes, pure configuration and resource-free AdminClient
remain attached to the application.

This is process safety, not leader election. Every Gunicorn worker that calls
`start_registry()` owns its own process-level Registry Worker. Flask-XXLJob does
not add a cross-process lock or automatically choose one worker.

## Flask and Celery sharing a factory

Initialize the protocol in both process types, but start Registry only in the
process that should renew the executor:

```python
def create_app(start_executor_registry=False):
    app = Flask(__name__)
    app.config["XXL_JOB_AUTO_REGISTER"] = False
    xxl_job.init_app(app)
    if start_executor_registry:
        xxl_job.start_registry(app)
    return app
```

Flask-XXLJob neither detects Celery nor creates Celery tasks.

## Exit removal and shared addresses

`XXL_JOB_DEREGISTER_ON_EXIT=False` is the default. Each process stops local
renewal during finalization but does not remove a shared Admin identity. Enable
it only when one Python process owns one exclusive executor address. Exit
removal is best-effort and the finalizer never waits for a Worker, Event,
cleanup actor, or Admin RPC; immediate interpreter exit, `SIGKILL`, and forced
container shutdown can prevent completion.

The exit path obeys the same lifecycle eligibility as explicit automatic
Remove: generation zero is not removed and one cleanup responsibility is
requested at most once. A later accepted register is a new remote state change,
not a failed-Remove retry, and may create a new responsibility in that same
generation. A one-shot `register_executor()` at generation zero does not create
a lifecycle and therefore is not automatically paired at exit; call
`remove_executor()` explicitly.

## Job timeout and logging

Task timeout remains an XXL-JOB Admin job setting, not a Registry setting. For
Celery or other async work, configure the Admin timeout and call
`callback_success()` or `callback_failure()` when work finishes.

For containers, prefer console-only managed logging. Managed Handler shutdown
is coordinated with outstanding Registry cleanup and closes at most once. A
standard rotating file handler is process-local and does not make one shared
file safe for multiple workers.

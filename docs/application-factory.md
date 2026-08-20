[English](application-factory.md) | [简体中文](application-factory.zh-CN.md)

# Application Factory

The Application Factory pattern is the default and recommended way to use
Flask-XXLJob. Create one module-level extension instance and initialize it
inside your factory.

```python
from flask import Flask
from flask_xxljob import FlaskXXLJob, XXLJobResponse

xxl_job = FlaskXXLJob()


@xxl_job.on_run("demoJobHandler")
def handle_run(request):
    return XXLJobResponse.success()


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
        XXL_JOB_ACCESS_TOKEN="",
        XXL_JOB_EXECUTOR_APP_NAME="project-executor",
        XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    )
    if config:
        app.config.update(config)

    xxl_job.init_app(app)
    return app
```

The Admin JobHandler must be exactly `demoJobHandler`. Module-level named
handlers are copied into each application when `init_app` runs.

With automatic Registry, defining module-level handlers before `init_app()` is
recommended so Admin does not briefly see an executor whose business handlers
are still being assembled. This is guidance, not a handler-ready state or
runtime restriction. If handlers must be registered per application after
initialization, set `XXL_JOB_AUTO_REGISTER=False`, call `init_app()`, register
the handlers, and finally call `start_registry(app)`.

## Per-application isolation

Each initialized application gets its own runtime stored in
`app.extensions["xxljob"]`, including its own configuration, callback registry,
clients and registry service. Callbacks registered while configuring one
application are not shared with another.

## Initialization boundary

`init_app()` validates deterministic configuration and Flask conflicts before
creating managed resources. Private prepare then starts an activation-gated
Thread when required and creates a detachable finalizer handle. The handle is
owned only by that initialization call: preparing it does not publish
`app.extensions`, the application registry, CLI, Blueprint, routes or hooks.
After Flask commit, only the Prepared creator may commit the generation/Worker
and wake the Thread. The Prepared stage performs no Admin RPC and is not a
running Registry lifecycle.

If private preparation fails, a started Prepared Thread is cancelled, the
finalizer is detached without closing the Runtime, owned handlers are closed,
no Flask extension resources have been committed, and the original exception is
preserved. During a later commit failure, only reversible CLI, extension and
application-registry entries still owned by this initialization are removed.
Flask-XXLJob does not mutate private Flask routing structures to provide a
general rollback.

## Direct initialization

Direct initialization is also supported:

```python
app = Flask(__name__)
xxl_job = FlaskXXLJob(app)
```

## Re-initialization

Calling `init_app()` twice for the same application raises
`XXLJobAlreadyInitializedError` instead of a confusing blueprint duplication
error.

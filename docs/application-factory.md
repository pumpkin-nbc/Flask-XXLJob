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

## Per-application isolation

Each initialized application gets its own runtime stored in
`app.extensions["xxljob"]`, including its own configuration, callback registry,
clients and registry service. Callbacks registered while configuring one
application are not shared with another.

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

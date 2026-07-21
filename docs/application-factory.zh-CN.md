[English](application-factory.md) | [简体中文](application-factory.zh-CN.md)

# Application Factory

Application Factory 模式是 Flask-XXLJob 的默认且推荐用法。创建一个模块级扩展实例，并在工厂函数内初始化它。

```python
from flask import Flask
from flask_xxljob import FlaskXXLJob, XXLJobResponse

xxl_job = FlaskXXLJob()


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
    register_xxljob_callbacks()
    return app


def register_xxljob_callbacks():
    @xxl_job.on_run
    def handle_run(request):
        return XXLJobResponse.success()
```

## 应用间隔离

每个已初始化的应用都拥有独立的 Runtime，保存在 `app.extensions["xxljob"]`，包含各自独立的配置、处理函数注册表、客户端与注册服务。为某个应用注册的处理函数不会与另一个应用共享。

## 直接初始化

同时支持直接初始化：

```python
app = Flask(__name__)
xxl_job = FlaskXXLJob(app)
```

## 重复初始化

对同一个应用调用两次 `init_app()` 会抛出 `XXLJobAlreadyInitializedError`，而不是难以理解的 Blueprint 重复注册错误。

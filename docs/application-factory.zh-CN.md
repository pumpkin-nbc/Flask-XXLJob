[English](application-factory.md) | [简体中文](application-factory.zh-CN.md)

# Application Factory

Application Factory 模式是 Flask-XXLJob 的默认且推荐用法。创建一个模块级扩展实例，并在工厂函数内初始化它。

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

Admin 中的 JobHandler 必须完全等于 `demoJobHandler`。模块级命名 Handler 会在
`init_app` 时复制到每个 Flask 应用。

## 应用间隔离

每个已初始化的应用都拥有独立的 Runtime，保存在 `app.extensions["xxljob"]`，包含各自独立的配置、处理函数注册表、客户端与注册服务。为某个应用注册的处理函数不会与另一个应用共享。

## 初始化边界

`init_app()` 会先校验确定性配置与 Flask 冲突，再创建托管资源。启用自动 Registry
时，它随后启动一个只在本地等待的 Prepared Thread，提交 Flask 扩展资源，最后才由
Prepared 创建者提交 generation/Worker 并唤醒线程。Prepared 阶段不执行 Admin RPC，
也不属于正在运行的 Registry lifecycle。

如果 `Thread.start()` 失败，本次初始化创建的 Handler 与其他私有资源会被关闭，Flask
扩展资源尚未提交，原始异常保持不变；修正系统条件后，可以用同一个 app 和扩展实例
再次调用 `init_app()`。Flask 不可逆 Commit 中的未知异常只会 best-effort 清理
Flask-XXLJob 自己拥有的私有资源，本项目不提供通用 Flask rollback。

## 直接初始化

同时支持直接初始化：

```python
app = Flask(__name__)
xxl_job = FlaskXXLJob(app)
```

## 重复初始化

对同一个应用调用两次 `init_app()` 会抛出 `XXLJobAlreadyInitializedError`，而不是难以理解的 Blueprint 重复注册错误。

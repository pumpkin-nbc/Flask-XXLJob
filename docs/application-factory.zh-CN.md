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

自动 Registry 模式推荐在 `init_app()` 前定义模块级 Handler，避免 Admin 短暂看到
执行器已经注册但业务 Handler 仍在组装。它只是使用建议，不会新增 handler-ready 状态
或运行时强制限制。必须在初始化后按应用注册 Handler 时，可先设置
`XXL_JOB_AUTO_REGISTER=False`，依次调用 `init_app()`、注册 Handler，最后调用
`start_registry(app)`。

## 应用间隔离

每个已初始化的应用都拥有独立的 Runtime，保存在 `app.extensions["xxljob"]`，包含各自独立的配置、处理函数注册表、客户端与注册服务。为某个应用注册的处理函数不会与另一个应用共享。

## 初始化边界

`init_app()` 会先校验确定性配置与 Flask 冲突，再创建托管资源。Private Prepare
会在需要时启动一个等待激活门的 Prepared Thread，并创建可 detach 的 finalizer
handle。这个 handle 只属于本次初始化；准备它不会写入 `app.extensions`、应用记录、
CLI、Blueprint、路由或 Hook。Flask Commit 后只有 Prepared 创建者可以提交
generation/Worker 并唤醒线程。Prepared 阶段不执行 Admin RPC，也不属于正在运行的
Registry lifecycle。

Private Prepare 失败时，已经启动的 Prepared 会被取消，finalizer 会在不关闭 Runtime
的情况下 detach，本次 Handler 会关闭，且原始异常保持不变。后续 Flask Commit 失败
时，只撤销本次仍持有 identity 的 CLI、extension 与应用记录等可逆状态；项目不会修改
Flask 私有路由结构来实现通用 rollback。当前 app 一旦接受本次 `init_app()`
创建的 exact Blueprint 对象，Blueprint 与 Runtime ownership 便同时视为已发布。
后续 activation 异常仍会传播，但不再删除 Runtime、CLI、应用记录或 finalizer。
已提交 Worker 的 activation Event 补发仍失败时，ownership 交由现有 Worker finally、
stop/shutdown 与 finalizer lifecycle 收敛。

## 直接初始化

同时支持直接初始化：

```python
app = Flask(__name__)
xxl_job = FlaskXXLJob(app)
```

## 重复初始化

对同一个应用调用两次 `init_app()` 会抛出 `XXLJobAlreadyInitializedError`，而不是难以理解的 Blueprint 重复注册错误。

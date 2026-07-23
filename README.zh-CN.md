[English](README.md) | [简体中文](README.zh-CN.md)

# Flask-XXLJob

一个实现官方 [XXL-JOB](https://github.com/xuxueli/xxl-job) 2.4.1 执行器协议的 Flask 扩展，使 Flask 项目可以直接作为 XXL-JOB 执行器，不再经过 Java 中转服务。

Flask-XXLJob 是一个**协议适配插件**。它只负责协议接入，**不负责**实际业务任务的执行。

## 功能特性

- 实现官方 XXL-JOB 2.4.1 执行器接口：`/beat`、`/idleBeat`、`/run`、`/kill`、`/log`。
- 使用普通请求处理函数（`on_run`、`on_idle_beat`、`on_kill`、`on_log`），不使用执行器适配器。
- 执行器注册 / 注销，并支持自动续约。
- 任务结果回调客户端（`callback`、`callback_success`、`callback_failure`）。
- 支持官方 `XXL-JOB-ACCESS-TOKEN` 请求头的 Access Token。
- 支持多个 Admin 地址并具备故障转移。
- 支持 Flask Application Factory 及应用间 Runtime 隔离。
- 严格校验协议字符串字段，并在启动时检测执行器路由冲突。
- 依赖最小化（`Flask`、`requests`），带类型标注（`py.typed`）。

## 不负责的内容

Flask-XXLJob 从不执行业务任务。它不创建线程池、进程池、任务队列、Celery 任务或消息队列；不管理任务状态、日志、超时或取消；也不会自动发送任务最终回调。你的 Flask 项目自行决定如何提交、执行、取消、记录日志并最终回调。

## 安装

```bash
pip install Flask-XXLJob
```

## 快速开始（Application Factory）

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

    @xxl_job.on_run
    def handle_run(request):
        # 将任务提交到你自己的任务服务，不要在这里执行任务。
        project_task_service.submit(
            handler=request.executor_handler,
            params=request.executor_params,
            job_id=request.job_id,
            log_id=request.log_id,
            log_date_time=request.log_date_time,
        )
        return XXLJobResponse.success()

    return app
```

## 任务结果回调

任务完成后，由你的项目主动回调 XXL-JOB：

```python
with app.app_context():
    xxl_job.callback_success(
        log_id=log_id,
        log_date_time=log_date_time,
        message="Task completed successfully.",
    )
```

## 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `XXL_JOB_ENABLED` | `True` | 是否启用扩展。 |
| `XXL_JOB_ADMIN_ADDRESSES` | `[]` | XXL-JOB Admin 基础地址列表。 |
| `XXL_JOB_ACCESS_TOKEN` | `""` | Access Token，空表示无 Token 模式。 |
| `XXL_JOB_EXECUTOR_APP_NAME` | `"flask-xxljob-executor"` | 执行器应用名称。 |
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | Admin 访问本执行器的地址。 |
| `XXL_JOB_ROUTE_PREFIX` | `""` | 执行器接口的 URL 前缀。 |
| `XXL_JOB_AUTO_REGISTER` | `True` | 是否启动自动注册续约。 |
| `XXL_JOB_REGISTRY_INTERVAL` | `30` | 注册续约间隔（秒）。 |
| `XXL_JOB_HTTP_CONNECT_TIMEOUT` | `3` | HTTP 连接超时（秒）。 |
| `XXL_JOB_HTTP_READ_TIMEOUT` | `5` | HTTP 读取超时（秒）。 |
| `XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH` | `10000` | `handleMsg` 最大长度（字符）。 |
| `XXL_JOB_MAX_REQUEST_SIZE` | `1048576` | 请求体最大字节数。 |
| `XXL_JOB_MAX_PARAM_LENGTH` | `65536` | `executorParams` 最大长度（字符）。 |
| `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` | `100` | `callback_many` 单批最大条目数。 |
| `XXL_JOB_ADMIN_RETRY_COUNT` | `0` | 同地址同步重试次数（有上限）。 |
| `XXL_JOB_ADMIN_RETRY_BACKOFF` | `0.0` | 重试之间的等待秒数（有上限）。 |
| `XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR` | `True` | 非 200 状态时故障转移。 |
| `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` | `False` | 非法 JSON 时故障转移。 |
| `XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR` | `False` | 业务失败时故障转移。 |

## 命令行

```bash
flask --app "project:create_app" xxljob register
flask --app "project:create_app" xxljob remove
flask --app "project:create_app" xxljob status
```

## 兼容性

目标支持 `Flask >= 1.0` 与 `Python >= 3.8`。兼容性矩阵（Python 3.8-3.13 x Flask 1/2/3）已在 `tox.ini` 与 `.github/workflows/ci.yml` 中配置。本版本已在 Python 3.12 与 Flask 3.0.3 上完成本地验证；其余组合已在 CI 中配置但未在本地执行。请在你自己的环境中运行测试后再声明特定组合可用。

当同一个 `FlaskXXLJob` 实例初始化了多个 Flask 应用时，请在应用上下文之外调用回调、注册、状态与生命周期辅助方法时显式传入 `app=`。只有恰好初始化了一个应用时才可省略；在初始化前注册的 `on_*` 装饰器仍会作为默认处理函数注入其后初始化的每个应用。

## 文档

参见 [docs](docs/) 目录，包括 [getting-started.md](docs/getting-started.md)、[configuration.md](docs/configuration.md)、[API 参考](docs/api-reference.zh-CN.md)与[集成测试](docs/integration-testing.zh-CN.md)。从旧版本升级？请参阅[迁移指南](docs/migration.zh-CN.md)与 [CHANGELOG](CHANGELOG.zh-CN.md)。

## 许可证

[Apache License 2.0](LICENSE)。署名信息参见 [NOTICE](NOTICE)。

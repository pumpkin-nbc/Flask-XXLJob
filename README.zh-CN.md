[English](README.md) | [简体中文](README.zh-CN.md)

# Flask-XXLJob

一个实现官方 [XXL-JOB](https://github.com/xuxueli/xxl-job) 2.4.1 执行器协议的 Flask 扩展，使 Flask 项目可以直接作为 XXL-JOB 执行器，不再经过 Java 中转服务。

Flask-XXLJob 是一个**协议适配插件**。它只负责协议接入，**不负责**实际业务任务的执行。

## 功能特性

- 实现官方 XXL-JOB 2.4.1 执行器接口：`/beat`、`/idleBeat`、`/run`、`/kill`、`/log`。
- 使用命名的 `on_run("名称")` 按 JobHandler 精确、区分大小写地自动分发。
- 执行器注册 / 注销，并支持自动续约。
- 任务结果回调客户端（`callback`、`callback_success`、`callback_failure`）。
- 支持官方 `XXL-JOB-ACCESS-TOKEN` 请求头的 Access Token。
- 支持多个 Admin 地址并具备故障转移。
- 支持 Flask Application Factory 及应用间 Runtime 隔离。
- 严格校验协议字符串字段，并在启动时检测执行器路由冲突。
- 提供可选、应用隔离的轮转文件与按等级着色的控制台插件诊断日志。
- 依赖最小化（`Flask`、`requests`），带类型标注（`py.typed`）。

## 不负责的内容

Flask-XXLJob 从不执行业务任务。它不创建线程池、进程池、任务队列、Celery 任务或消息队列；不管理任务状态、日志、超时或取消；也不会自动发送任务最终回调。你的 Flask 项目自行决定如何提交、执行、取消、记录日志并最终回调。

## 安装

```bash
pip install Flask-XXLJob
```

## 五分钟快速开始

如果你刚开始学习 Python、Flask 或 XXL-JOB，请直接按照
[Python 入门者指南](docs/getting-started.zh-CN.md)操作。教程第一阶段不要求安装 XXL-JOB Admin。

```python
from flask import Flask
from flask_xxljob import FlaskXXLJob, XXLJobResponse

app = Flask(__name__)
app.config.update(
    XXL_JOB_AUTO_REGISTER=False,  # 先在本地运行，不连接 Admin
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
)
xxl_job = FlaskXXLJob(app)


@xxl_job.on_run("demoJobHandler")
def handle_run(request):
    print("任务：", request.job_id, "参数：", request.parse_params())
    return XXLJobResponse.success(content="任务已收到")


app.run(port=5001)
```

在 Admin 中把任务的 JobHandler 填为完全一致的 `demoJobHandler`。Flask-XXLJob 会自动
校验并分发；未知名称返回 XXL-JOB `code=500`，不会误调用其他处理函数。

保存为 `app.py`，然后运行：

```bash
python app.py
```

仓库中提供了经过测试的版本：
[`examples/beginner/app.py`](examples/beginner/app.py)。先确认本地
`/xxl-job/run` 测试成功，再连接 Admin。

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
| `XXL_JOB_LOG_ENABLED` | `False` | 是否启用插件托管的诊断日志 Handler。 |
| `XXL_JOB_LOG_FILE_ENABLED` | `True` | 是否写入轮转日志文件。 |
| `XXL_JOB_LOG_CONSOLE_ENABLED` | `True` | 是否将正常与异常日志统一写入控制台。 |
| `XXL_JOB_LOG_LEVEL` | `"INFO"` | 托管 Handler 共用的日志等级。 |
| `XXL_JOB_LOG_FORMAT` | 标准格式 | 共用的 Python Logging 格式。 |
| `XXL_JOB_LOG_DATE_FORMAT` | `"%Y-%m-%d %H:%M:%S"` | 时间格式。 |
| `XXL_JOB_LOG_PATH` | `"./logs"` | 文件日志目录，相对进程当前工作目录。 |
| `XXL_JOB_LOG_FILENAME` | `"flask-xxljob.log"` | 日志文件名。 |
| `XXL_JOB_LOG_ENCODING` | `"utf-8"` | 文件编码。 |
| `XXL_JOB_LOG_MAX_BYTES` | `10485760` | 单个日志文件的轮转字节数。 |
| `XXL_JOB_LOG_BACKUP_COUNT` | `5` | 轮转备份数量。 |
| `XXL_JOB_LOG_PROPAGATE` | `False` | 存在托管 Handler 时是否继续传播。 |

托管日志默认关闭，不创建目录、文件或控制台 Handler。只开启
`XXL_JOB_LOG_ENABLED` 时默认同时写入 `./logs/flask-xxljob.log` 和控制台；容器环境
建议关闭文件目标并保留默认控制台目标。详见[日志指南](docs/logging.zh-CN.md)。

## 命令行

```bash
flask --app "project:create_app" xxljob register
flask --app "project:create_app" xxljob remove
flask --app "project:create_app" xxljob status
```

## 兼容性

目标支持 `Flask >= 1.0` 与 `Python >= 3.8`。兼容性矩阵
（Python 3.8-3.14 x Flask 1/2/3）已在 `tox.ini` 与
`.github/workflows/ci.yml` 中配置。本版本已在 Python 3.12.13 与 Flask 3.1.3
上完成本地验证；其余组合已在 CI 中配置但未在本地执行。请在你自己的环境中
运行测试后再声明特定组合可用。

当同一个 `FlaskXXLJob` 实例初始化了多个 Flask 应用时，请在应用上下文之外调用回调、注册、状态与生命周期辅助方法时显式传入 `app=`。只有恰好初始化了一个应用时才可省略；在初始化前注册的 `on_*` 装饰器仍会作为默认处理函数注入其后初始化的每个应用。

## 文档

参见 [docs](docs/) 目录，包括 [Python 入门者指南](docs/getting-started.zh-CN.md)、[配置](docs/configuration.zh-CN.md)、[日志指南](docs/logging.zh-CN.md)、[API 参考](docs/api-reference.zh-CN.md)与[集成测试](docs/integration-testing.zh-CN.md)。端到端 Flask 接入可直接参考[完整接入案例](examples/complete_integration/README.zh-CN.md)。从旧版本升级？请参阅[迁移指南](docs/migration.zh-CN.md)与 [CHANGELOG](CHANGELOG.zh-CN.md)。

## 许可证

[Apache License 2.0](LICENSE)。署名信息参见 [NOTICE](NOTICE)。

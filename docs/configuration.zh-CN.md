[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# 配置

所有配置都在 `init_app()` 阶段从 `app.config` 读取。扩展从不在模块导入阶段读取配置，也不在构造函数中访问 `current_app`。

## 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `XXL_JOB_ENABLED` | `True` | 是否启用扩展。 |
| `XXL_JOB_ADMIN_ADDRESSES` | `[]` | XXL-JOB Admin 基础地址列表。 |
| `XXL_JOB_ACCESS_TOKEN` | `""` | Access Token，空表示无 Token 模式。 |
| `XXL_JOB_EXECUTOR_APP_NAME` | `"flask-xxljob-executor"` | 执行器应用名称。 |
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | 执行器服务基础地址（协议/主机/端口）；会自动附加 `XXL_JOB_ROUTE_PREFIX`。 |
| `XXL_JOB_ROUTE_PREFIX` | `""` | 执行器接口的 URL 前缀；同时会附加到 `XXL_JOB_EXECUTOR_ADDRESS`。 |
| `XXL_JOB_AUTO_REGISTER` | `True` | 是否启动自动注册续约。 |
| `XXL_JOB_AUTO_REGISTER_ON_INIT` | `True` | 启用自动注册时，是否在 `init_app()` 阶段启动续约。 |
| `XXL_JOB_DEREGISTER_ON_EXIT` | `True` | Runtime 自动关闭时是否注销执行器。 |
| `XXL_JOB_REGISTRY_INTERVAL` | `30` | 注册续约间隔（秒）。 |
| `XXL_JOB_HTTP_CONNECT_TIMEOUT` | `3` | HTTP 连接超时（秒）。 |
| `XXL_JOB_HTTP_READ_TIMEOUT` | `5` | HTTP 读取超时（秒）。 |
| `XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH` | `10000` | `handleMsg` 最大长度（字符）。 |
| `XXL_JOB_MAX_REQUEST_SIZE` | `1048576` | 请求体最大字节数。 |
| `XXL_JOB_MAX_PARAM_LENGTH` | `65536` | `executorParams` 最大长度（字符）。 |
| `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` | `100` | `callback_many` 单批最大条目数。 |
| `XXL_JOB_ADMIN_RETRY_COUNT` | `0` | 瞬时错误的同地址同步重试次数（有上限）。 |
| `XXL_JOB_ADMIN_RETRY_BACKOFF` | `0.0` | 重试之间的等待秒数（有上限）。 |
| `XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR` | `True` | 非 200 状态时尝试下一个 Admin。 |
| `XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON` | `False` | 非法 JSON 响应时尝试下一个 Admin。 |
| `XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR` | `False` | 业务码失败时尝试下一个 Admin。 |
| `XXL_JOB_LOG_ENABLED` | `False` | 是否启用插件托管日志。 |
| `XXL_JOB_LOG_FILE_ENABLED` | `True` | 托管日志开启时是否添加轮转文件 Handler。 |
| `XXL_JOB_LOG_CONSOLE_ENABLED` | `True` | 是否用同一个控制台 Handler 输出正常与异常记录。 |
| `XXL_JOB_LOG_LEVEL` | `"INFO"` | 共用等级：`DEBUG`、`INFO`、`WARNING`、`ERROR` 或 `CRITICAL`。 |
| `XXL_JOB_LOG_FORMAT` | `"%(asctime)s [%(levelname)s] [%(name)s] %(message)s"` | 共用的标准 Logging 格式。 |
| `XXL_JOB_LOG_DATE_FORMAT` | `"%Y-%m-%d %H:%M:%S"` | Formatter 时间格式；空字符串使用 Logging 默认值。 |
| `XXL_JOB_LOG_PATH` | `"./logs"` | 日志目录；相对路径按进程当前工作目录解析。 |
| `XXL_JOB_LOG_FILENAME` | `"flask-xxljob.log"` | 日志文件名。 |
| `XXL_JOB_LOG_ENCODING` | `"utf-8"` | 有效的 Python 文本编码。 |
| `XXL_JOB_LOG_MAX_BYTES` | `10485760` | 正整数轮转字节阈值。 |
| `XXL_JOB_LOG_BACKUP_COUNT` | `5` | 非负轮转备份数量。 |
| `XXL_JOB_LOG_PROPAGATE` | `False` | 存在托管输出目标时是否继续传播日志。 |

请求大小以**字节**计量；`handleMsg` 与 `executorParams` 长度以**字符**（Unicode
码点）计量，因此中文等多字节字符每个计为一个字符。

无论上述故障转移开关如何设置，网络与超时错误始终会转移到下一个 Admin。

## 示例

```python
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=[
        "http://admin-1:8080/xxl-job-admin",
        "http://admin-2:8080/xxl-job-admin",
    ],
    XXL_JOB_ACCESS_TOKEN="",
    XXL_JOB_EXECUTOR_APP_NAME="project-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_AUTO_REGISTER=True,
    XXL_JOB_AUTO_REGISTER_ON_INIT=True,
    XXL_JOB_DEREGISTER_ON_EXIT=True,
    XXL_JOB_REGISTRY_INTERVAL=30,
)
```

## Registry 生命周期

`XXL_JOB_AUTO_REGISTER` 控制是否使用自动注册续约，
`XXL_JOB_AUTO_REGISTER_ON_INIT` 控制该生命周期何时启动。

| `AUTO_REGISTER` | `AUTO_REGISTER_ON_INIT` | `init_app()` 行为 |
| --- | --- | --- |
| `True` | `True` | 启动后台注册线程。 |
| `True` | `False` | 只初始化，等待 `start_registry(app)`。 |
| `False` | `True` | 不自动启动。 |
| `False` | `False` | 不自动启动。 |

`XXL_JOB_DEREGISTER_ON_EXIT` 只影响 Runtime 自动清理。显式调用
`stop_registry()` 默认仍会注销；使用 `stop_registry(remove=False)` 可只停止续约，
不删除共享的执行器身份。

## 校验

配置在 `init_app()` 时校验。类型错误会抛出 `XXLJobConfigError`。`XXL_JOB_EXECUTOR_APP_NAME`、至少一个 `XXL_JOB_ADMIN_ADDRESSES` 条目以及 `XXL_JOB_EXECUTOR_ADDRESS` 仅在启用 `XXL_JOB_AUTO_REGISTER` 时才是必填项，因此仅做协议接入而不注册的部署可以省略它们。提供 Admin/执行器地址时必须使用 `http` 或 `https` 方案，包含主机与合法端口，同时允许上下文路径。Admin 与执行器地址在加载时会被规范化（去除首尾空格与多余尾部斜杠，同时保留上下文路径与顺序）。设置了 `XXL_JOB_ROUTE_PREFIX` 时会始终附加到 `XXL_JOB_EXECUTOR_ADDRESS`；请勿在执行器地址中再手写该前缀。只含空白的 Access Token 会被规范化为空（无 Token 模式），非空 Token 保持原值。校验错误信息会指明出错的配置项、其收到的类型以及期望格式。错误配置绝不会被静默忽略。

所有布尔配置只接受真正的布尔值。等级、编码、轮转值与日志格式均在初始化
阶段校验；格式会使用模拟 `LogRecord` 实际格式化一次，因此未知字段会在应用启动前
失败。托管日志关闭或两个输出目标都关闭时，扩展不会覆盖 Runtime Logger 的等级和
传播设置，宿主可以自行配置 `flask_xxljob` Logger。详见[日志](logging.zh-CN.md)。

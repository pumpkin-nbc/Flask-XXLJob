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
| `XXL_JOB_AUTO_REGISTER` | `True` | 与 `ENABLED=True` 同时成立时，在 `init_app()` 后启动 Registry。 |
| `XXL_JOB_DEREGISTER_ON_EXIT` | `False` | Runtime 关闭时是否申请 best-effort 后台注销。 |
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
    XXL_JOB_DEREGISTER_ON_EXIT=False,
    XXL_JOB_REGISTRY_INTERVAL=30,
)
```

## Registry 生命周期

唯一自动启动条件是 `XXL_JOB_ENABLED and XXL_JOB_AUTO_REGISTER`。条件成立时，
`init_app()` 会先完成 Runtime、五个 HTTP 路由和 finalizer 初始化，再调用公开
`start_registry(app)`。`AUTO_REGISTER=False` 时只初始化执行器协议能力，业务可稍后
显式启动 Registry。

`stop_registry()` 默认只做本地停止：唤醒并分离当前续约 Worker，不 join、不访问
Admin，也不修改 `registered`。`stop_registry(remove=True)` 会同步校验 Registry
配置，并为最近一个非零 lifecycle generation 至多申请一次后台 `registryRemove`。
需要确定性结果时，先调用 `stop_registry()`，再调用 `remove_executor()`。

退出注销默认关闭。显式开启后仍是非阻塞 best-effort；解释器立即退出、`SIGKILL`
或容器强制终止都可能使其无法完成。

## 校验

校验分三层：首先始终检查已经删除的配置键，即使 `XXL_JOB_ENABLED=False` 也不
跳过；随后在 `init_app()` 执行现有字段类型和值校验；最后仅在 enabled 状态真正调用
`start_registry()`、`register_executor()`、`remove_executor()` 或
`stop_registry(remove=True)` 前校验完整 Registry 配置。因此
`AUTO_REGISTER=False` 的纯协议初始化可以不提供 Admin 与执行器 Registry 配置。
提供 Admin/执行器地址时必须使用 `http` 或 `https` 方案，包含主机与合法端口，同时
允许上下文路径。地址会在加载时规范化，`XXL_JOB_ROUTE_PREFIX` 会始终附加到执行器
地址。错误配置绝不会被静默忽略。

所有布尔配置只接受真正的布尔值。等级、编码、轮转值与日志格式均在初始化
阶段校验；格式会使用模拟 `LogRecord` 实际格式化一次，因此未知字段会在应用启动前
失败。托管日志关闭或两个输出目标都关闭时，扩展不会覆盖 Runtime Logger 的等级和
传播设置，宿主可以自行配置 `flask_xxljob` Logger。详见[日志](logging.zh-CN.md)。

`XXL_JOB_ENABLED=False` 时，Registry API 会在完整校验、线程、Remove、网络锁、RPC
与 sequence 分配之前短路。两个同步单次 API 返回
`error="Flask-XXLJob is disabled."` 的配置失败 `CallResult`，只更新当前进程的安全
本地失败快照，并保持 `registered` 不变。

[English](api-reference.md) | [简体中文](api-reference.zh-CN.md)

# API 参考

本页记录 Flask-XXLJob 0.3.3 的公共 API。该扩展只负责适配 XXL-JOB 2.4.1 协议，
绝不执行业务任务。

## `FlaskXXLJob`

扩展主类。

```python
from flask_xxljob import FlaskXXLJob

xxl_job = FlaskXXLJob()          # 延迟初始化
xxl_job.init_app(app)            # 或 FlaskXXLJob(app)
```

### 请求处理函数注册（装饰器）

`on_run(executor_handler)` 注册命名的扩展级 Run Handler。名称必须是没有首尾空格的
非空字符串，并按精确、区分大小写的方式匹配；其他 `on_*` 装饰器仍不带名称。
初始化前注册的 Handler 会注入其后初始化的每个应用。

```python
@xxl_job.on_run("demoJobHandler")
def handle_run(request):
    return XXLJobResponse.success()

# 另有：on_idle_beat、on_kill、on_log
```

### 应用级注册

为指定应用注册或读取处理函数。`app=None` 时优先使用当前应用上下文；在上下文之外，只有恰好初始化了一个应用时才能省略 `app`。若已初始化多个应用，必须显式传入 `app`，否则抛出 `XXLJobError`。

```python
xxl_job.register_callbacks(
    app,
    run={"demoJobHandler": handle_run, "reportJobHandler": handle_report},
    replace=False,
)
xxl_job.set_run_callback(app, "demoJobHandler", handle_run, replace=True)
handler = xxl_job.get_run_callback(app, "demoJobHandler")
# 另有：set_idle_beat_callback / set_kill_callback / set_log_callback
#       get_idle_beat_callback / get_kill_callback / get_log_callback
```

非法名称、不可调用的值或重复名称会抛出 `XXLJobCallbackRegistrationError`；
重复名称只有在 `replace=True` 时才会覆盖。`register_callbacks` 会先校验完整批次，
失败时注册表保持不变。请求名称未匹配时返回 HTTP 200、XXL-JOB `code=500` 及
`Unsupported JobHandler: <name>`；不存在默认兜底 Run Handler。

### 执行器注册

```python
result = xxl_job.register_executor(app)   # CallResult
result = xxl_job.remove_executor(app)     # CallResult
```

### 任务结果回调

```python
xxl_job.callback(log_id, log_date_time, handle_code, handle_msg=None, app=None)
xxl_job.callback_success(log_id, log_date_time, message=None, app=None)
xxl_job.callback_failure(log_id, log_date_time, message=None, app=None)
xxl_job.callback_many(callbacks, app=None)   # CallbackRequest 或 dict 的列表
```

`callback_many` 发送前会校验每一条，绝不自动拆分；任一条目非法或数量超过
`XXL_JOB_CALLBACK_BATCH_MAX_SIZE` 时整体拒绝且不发送任何数据。

### 状态与生命周期

```python
status = xxl_job.get_status(app)   # XXLJobStatus
xxl_job.start_registry(app)
xxl_job.stop_registry(app)
```

## 请求模型

传入你的处理函数；所有字段均为类型化且 Unicode 安全。协议字符串字段只接受字符串；字段缺失或为 `None` 时采用该字段默认值。整数、布尔、数组与对象会被拒绝：执行器端点返回 XXL-JOB `code=500` 响应，出站回调 API 则在发送前抛出 `XXLJobValidationError`。

```python
from flask_xxljob import (
    TriggerRequest, IdleBeatRequest, KillRequest, LogRequest, RegistryRequest,
    CallbackRequest,
)
```

## 响应模型

```python
from flask_xxljob import XXLJobResponse, LogResponse

XXLJobResponse.success(content=None, msg=None)
XXLJobResponse.failure("message")
```

## `CallResult` / `AdminCallResult`

单次 Admin API 调用的结果（`AdminCallResult` 为别名）。

```python
result.success        # bool
result.code           # Optional[int]  Admin 返回的业务码
result.msg            # Optional[str]
result.message        # msg，缺失时返回 error
result.address        # 产生该结果的 Admin 地址
result.admin_address  # address 的别名
result.error          # 本地错误字符串（绝不含 Token）
result.error_type     # None | 'network' | 'timeout' | 'http'
                      #      | 'invalid_json' | 'business' | 'config'
result.attempt_count  # 总 HTTP 请求次数
result.elapsed_ms     # 总耗时（毫秒）
result.http_status    # 最近一次 HTTP 状态码（若有）
```

## `XXLJobStatus`

插件的只读状态快照（绝不含 Token 或业务任务状态）。

```python
status.enabled
status.auto_register
status.registered
status.last_registry_time
status.last_registry_success
status.last_registry_admin_address
status.last_registry_error_type
status.last_registry_message
status.registry_thread_running
status.log_enabled
status.log_level
status.log_file_enabled
status.log_console_enabled
status.log_file
```

日志字段描述实际生效的托管输出目标。文件日志生效时 `log_file` 是解析后的绝对路径，
否则为 `None`。状态与 CLI 输出绝不包含 Access Token，也不能动态修改日志配置。

## 异常

所有异常都继承 `FlaskXXLJobError`。旧名称保留为别名。

```python
from flask_xxljob import (
    FlaskXXLJobError,            # 基类
    XXLJobError,                # FlaskXXLJobError 的别名
    XXLJobConfigurationError,   # XXLJobConfigError（别名）
    XXLJobInitializationError,
    XXLJobAlreadyInitializedError,
    XXLJobCallbackRegistrationError,
    XXLJobValidationError,      # XXLJobRequestError（别名）
    XXLJobProtocolError,
    XXLJobAdminCallError,
    XXLJobCallbackError,
    XXLJobRegistryError,
)
```

## CLI

```bash
flask xxljob register
flask xxljob remove
flask xxljob status
```

配置项完整列表见 [配置](configuration.zh-CN.md)。

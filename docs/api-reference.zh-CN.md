[English](api-reference.md) | [简体中文](api-reference.zh-CN.md)

# API 参考

本页记录 Flask-XXLJob 0.3.0 的公共 API。该扩展只负责适配 XXL-JOB 2.4.1 协议，
绝不执行业务任务。

## `FlaskXXLJob`

扩展主类。

```python
from flask_xxljob import FlaskXXLJob

xxl_job = FlaskXXLJob()          # 延迟初始化
xxl_job.init_app(app)            # 或 FlaskXXLJob(app)
```

### 请求处理函数注册（装饰器）

`on_*` 装饰器注册默认（扩展级）处理函数，并在其后初始化的每个应用中被注入。

```python
@xxl_job.on_run
def handle_run(request):
    return XXLJobResponse.success()

# 另有：on_idle_beat、on_kill、on_log
```

### 应用级注册

为指定应用注册或读取处理函数。`app=None` 时优先使用当前应用上下文；在上下文之外，只有恰好初始化了一个应用时才能省略 `app`。若已初始化多个应用，必须显式传入 `app`，否则抛出 `XXLJobError`。

```python
xxl_job.register_callbacks(app, run=handle_run, replace=False)
xxl_job.set_run_callback(app, handle_run, replace=True)
handler = xxl_job.get_run_callback(app)
# 另有：set_idle_beat_callback / set_kill_callback / set_log_callback
#       get_idle_beat_callback / get_kill_callback / get_log_callback
```

除非 `replace=True`，否则重复注册同一处理函数会抛出
`XXLJobCallbackRegistrationError`。

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

XXLJobResponse.success(content=None)
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
```

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

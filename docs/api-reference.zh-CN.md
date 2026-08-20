[English](api-reference.md) | [简体中文](api-reference.zh-CN.md)

# API 参考

本页记录 Flask-XXLJob 0.4.0 的公共 API。该扩展只负责适配 XXL-JOB 2.4.1 协议，
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

二者都是同步单次 Admin 操作，共用当前进程的 Registry 网络锁，但不会启动或停止
lifecycle，也不会推进 generation。当前仍有续约 Worker 时，`remove_executor()` 保持
普通单次 RPC，不消耗 lifecycle 清理状态。非零 generation 已停止后，同一个 API 会
参与终止型 Active/Pending ownership，使成功的同步 Remove 可被 shutdown 复用而不会
重复发送。调用失败时保留原有 `registered` 快照；扩展 disabled 时返回本地配置失败
`CallResult`，不执行 Admin RPC。

对于有效的非零 generation，显式 `register_executor()` 会在等待网络锁前加入该代仍
开放的 Register Coordination。此后 lifecycle cleanup 若完成线性化，shutdown 仍然
非阻塞，只把 Remove 延后到这些已参与调用全部结束。协调窗口关闭后才开始的调用保持
原有 one-shot API 语义。

真实 one-shot Register completion 是否接受，只取决于 strict sequence 与调用捕获的
ProcessState identity。generation 或 Coordination 变化不能抹掉已经发生的 Admin RPC：
accepted success 仍会设置 `registered=True` 并推进 applied sequence。生命周期 identity
另行决定该成功能否重新产生清理责任，因此旧 generation completion 不会修改新代的
cleanup cache、Coordination、Pending 或 Active ownership。

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
xxl_job.stop_registry(app)                  # 本地停止，立即返回
xxl_job.stop_registry(app, remove=True)     # 增加一次后台注销
```

`start_registry()` 会同步校验完整 Registry 配置，为当前进程至多建立一个有效的
daemon 续约 Worker，并在首次 Admin 调用完成前返回。`stop_registry()` 的 `remove`
是仅限关键字参数，默认 `False`：它立即分离并唤醒 Worker，不 join、不访问 Admin，
并保留最近的 `registered` 快照。因此 `registry_thread_running=False` 与
`registered=True` 可以同时成立。

`init_app()` 自动启动 Registry 时，会把同一私有 Worker lifecycle 拆成两段：Flask
Commit 前先创建 OS Thread，但它只等待激活门且 Admin RPC 为零；Commit 后只有创建
该 Prepared token 的调用者才能提交 generation/Worker 并唤醒线程。Prepared ownership
不会被状态接口报告为 Registry Thread 正在运行。并发 Registry stop 或 shutdown 可以
正常取消候选；一旦正式提交，所有 Worker early return（包括首次 RPC 前已经 stop）都
仍位于正常 Worker `try/finally` 收尾边界内。

`stop_registry(remove=True)` 先校验配置，再完成同样的本地停止，并为当前清理责任
排队一次后台 `registryRemove`。终止 Remove 成功后该责任即满足；如果同 generation
后来又有 accepted register 重新建立远端身份，则会产生一份新的必要清理责任，这不
是 Remove 失败后的自动重试。需要确定性同步结果时使用：

```python
xxl_job.stop_registry(app)
result = xxl_job.remove_executor(app)
```

全部 Registry 状态都属于当前进程。所有本地读取先检查 PID；fork 子进程会获得空白
锁、Worker/Remove ownership、sequence 和快照，且不获取父进程锁。状态查询不访问
Admin，也不创建线程。正常续约仍是立即注册，再按 `REGISTRY_INTERVAL` 等待。

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

XXLJobResponse.success(msg=None, content=None)
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

`xxljob remove` 会先停止当前本地 Registry 续约生命周期，再执行一次同步 Remove。
Admin 注销失败时命令返回非零退出码，但不会重新启动续约。这一终止型 CLI 语义与公开
低层 `remove_executor()` 有意区分；后者只执行一次同步 RPC，不停止 Worker。

配置项完整列表见 [配置](configuration.zh-CN.md)。

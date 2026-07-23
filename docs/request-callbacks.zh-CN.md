[English](request-callbacks.md) | [简体中文](request-callbacks.zh-CN.md)

# 请求处理函数

Flask-XXLJob 不使用执行器适配器。你只需注册接收类型化请求模型的普通函数。这些函数是 XXL-JOB 请求处理函数，而不是业务任务 Handler。

## 注册

四个处理函数都可以作为方法或装饰器使用：

```python
@xxl_job.on_run
def handle_run(request):
    task_id = project_task_service.submit(
        task_name=request.executor_handler,
        task_params=request.executor_params,
        job_id=request.job_id,
        log_id=request.log_id,
        log_date_time=request.log_date_time,
    )
    if task_id is None:
        return XXLJobResponse.failure("submit task failed")
    return XXLJobResponse.success()


@xxl_job.on_idle_beat
def handle_idle_beat(request):
    if project_task_service.is_running(request.job_id):
        return XXLJobResponse.failure("job is running")
    return XXLJobResponse.success()


@xxl_job.on_kill
def handle_kill(request):
    if not project_task_service.cancel(request.job_id):
        return XXLJobResponse.failure("kill task failed")
    return XXLJobResponse.success()


@xxl_job.on_log
def handle_log(request):
    return project_task_service.read_log(
        log_id=request.log_id,
        from_line_num=request.from_line_num,
    )
```

## 注册时机

处理函数可以在 `init_app` 之前或之后注册。在模块级（`init_app` 之前）注册已完全支持，也是 Application Factory 模式推荐的写法：

```python
xxl_job = FlaskXXLJob()

@xxl_job.on_run
def handle_run(request):
    return XXLJobResponse.success()

def create_app():
    app = Flask(__name__)
    xxl_job.init_app(app)
    return app
```

模块级注册的处理函数会成为该扩展初始化的每个应用的默认处理函数。

## 应用级注册

除 `on_*` 装饰器外，你还可以为指定应用注册处理函数。这在应用工厂或多应用场景中很有用：

```python
def create_app():
    app = Flask(__name__)
    xxl_job.init_app(app)
    xxl_job.register_callbacks(app, run=handle_run, log=handle_log)
    # 或：xxl_job.set_run_callback(app, handle_run, replace=True)
    return app
```

使用 `get_run_callback(app)`（以及 `idle_beat`/`kill`/`log` 变体）读取当前已注册的处理函数。当 `app=None` 时使用当前应用上下文；在上下文之外，恰好初始化一个应用时可以省略，初始化多个应用后则必须显式传入 `app`。

请求分发时的解析优先级：先检查应用级注册表，再检查由 `on_*` 装饰器设置的扩展级默认。两者都未配置时，接口返回标准的“未配置”失败。

## 重复注册

重复注册同一处理函数会抛出 `XXLJobCallbackRegistrationError`（`FlaskXXLJobError` 的子类）。向 `register_callbacks`/`set_*_callback` 传入 `replace=True` 可有意覆盖已有处理函数。

## 返回值

`on_run`、`on_idle_beat` 与 `on_kill` 返回 `XXLJobResponse`。`on_log` 返回 `LogResponse`。返回其他类型（包括 `None`、`dict`、`str`、`bool`）会返回明确的 “unsupported response type” 失败，而不是内部错误。

## 未注册处理函数

如果未注册处理函数，对应接口会返回明确的失败信息，例如 `XXL-JOB run callback is not configured`；绝不会静默返回成功。

## 参数

`TriggerRequest.parse_params()` 解析 `executor_params` 且不修改原始值：空值返回 `None`，合法 JSON 返回解析后的对象，否则返回原始字符串。

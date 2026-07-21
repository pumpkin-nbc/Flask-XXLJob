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

## 返回值

`on_run`、`on_idle_beat` 与 `on_kill` 返回 `XXLJobResponse`。`on_log` 返回 `LogResponse`。

## 未注册处理函数

如果未注册处理函数，对应接口会返回明确的失败信息，例如 `XXL-JOB run callback is not configured`；绝不会静默返回成功。

## 参数

`TriggerRequest.parse_params()` 解析 `executor_params` 且不修改原始值：空值返回 `None`，合法 JSON 返回解析后的对象，否则返回原始字符串。

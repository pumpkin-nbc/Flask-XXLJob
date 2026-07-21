[English](callback.md) | [简体中文](callback.zh-CN.md)

# 任务结果回调

Flask-XXLJob 从不判断任务何时完成，也不会自动发送最终回调。任务完成后，由你的项目主动调用回调 API。

## API

```python
xxl_job.callback_success(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    message="Task completed successfully.",
)

xxl_job.callback_failure(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    message="Task execution failed.",
)

xxl_job.callback(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    handle_code=200,
    handle_msg="Task completed successfully.",
)
```

## 在应用上下文中

在 Flask 应用上下文中可以省略 `app` 参数：

```python
with app.app_context():
    xxl_job.callback_success(
        log_id=log_id,
        log_date_time=log_date_time,
        message="Task completed successfully.",
    )
```

## 行为

回调客户端构造官方请求（向 `/api/callback` 发送单元素 `HandleCallbackParam` 数组），携带 Access Token，应用连接与读取超时，将 `handleMsg` 截断到配置的最大长度，按顺序尝试多个 Admin 地址，并返回明确的结果。它不持久化回调、不在后台无限重试，也不创建后台线程。

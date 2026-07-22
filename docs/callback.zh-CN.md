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

## 批量回调

若要在一次官方请求中上报多个任务结果，使用 `callback_many`：

```python
from flask_xxljob import CallbackRequest

xxl_job.callback_many(
    [
        CallbackRequest(log_id=1, log_date_time=1710000000000, handle_code=200),
        CallbackRequest(log_id=2, log_date_time=1710000000000, handle_code=500,
                        handle_msg="failed"),
    ],
    app=app,
)
```

发送前会校验每一条。批量绝不自动拆分；任一条目非法或数量超过
`XXL_JOB_CALLBACK_BATCH_MAX_SIZE` 时整体拒绝（全有或全无），不投递任何数据。

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

回调客户端构造官方请求（向 `/api/callback` 发送单元素 `HandleCallbackParam` 数组），携带 Access Token，应用连接与读取超时，将 `handleMsg` 截断到配置的最大长度，并返回明确的结果。它不持久化回调、不在后台无限重试，也不创建后台线程。

`message` 默认为 `None`（按空信息处理）。`log_id` 与 `log_date_time` 必须是整数；传入布尔值或非整数会抛出 `XXLJobRequestError`。

配置多个 Admin 地址时，回调会在第一个返回有效业务响应（成功或失败）的地址处停止，避免重复投递同一回调；仅在网络错误、非 200 状态或非法 JSON 时才切换到下一个地址。返回的 `CallResult`（同时导出为 `AdminCallResult`）提供 `success`、`code`、`msg`/`message`、`address`/`admin_address` 与 `error_type`。`error_type` 将失败归类为 `network`、`timeout`、`http`、`invalid_json`、`business` 或 `config` 之一（成功时为 `None`），因此无需检查 `requests` 即可作出响应。结果还包含 `attempt_count`、`elapsed_ms` 与 `http_status` 便于排查。故障转移与有限的同步重试由 `XXL_JOB_ADMIN_*` 配置项控制；默认情况下业务失败不会重复发送到其他 Admin。

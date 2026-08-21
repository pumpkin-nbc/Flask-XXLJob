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

配置多个 Admin 地址时，回调会在第一个返回有效业务响应（成功或失败）的地址处停止，
避免重复投递同一回调；仅在网络错误、非 200 状态、非法 JSON 或非法响应对象时才按
配置切换地址。Admin POST 不跟随重定向。解析结果必须是对象，`code` 必须是非 bool
整数，`msg` 必须是字符串或 `None`，且只有 `code=200` 成功。返回的 `CallResult`
（同时导出为 `AdminCallResult`）提供 `success`、`code`、`msg`/`message`、`address`/
`admin_address` 与 `error_type`。`error_type` 将失败归类为 `network`、`timeout`、`http`、
`invalid_json`、`invalid_response`、`business` 或 `config` 之一（成功时为 `None`），
因此无需检查 `requests` 即可作出响应。结果还包含 `attempt_count`、`elapsed_ms` 与
`http_status` 便于排查。故障转移与有限的同步重试由 `XXL_JOB_ADMIN_*` 配置项控制；
默认情况下业务失败不会重复发送到其他 Admin。

`XXL_JOB_ENABLED=False` 是完整功能总开关，四种公共 Callback 都返回本地 disabled
`CallResult` 且不发送 Admin HTTP。调用仍先解析目标应用 Runtime，因此未初始化和多应用
歧义继续报错；确认该 Runtime disabled 后，不再校验、规范化、复制或遍历 Callback
负载。enabled 下的消息转换、校验与截断规则完全保持原样。只需要 Callback、不维护
Registry 续约的进程应使用 `XXL_JOB_ENABLED=True` 与
`XXL_JOB_AUTO_REGISTER=False`。

## 长任务（Celery 等）

Flask-XXLJob 不执行、也不管理业务任务超时。对接 Celery 或其他异步 worker 时：

1. 在 `on_run` 中尽快投递任务并返回 `XXLJobResponse.success(...)`，把
   `log_id`、`log_date_time` 原样传给 worker。
2. worker 结束后调用 `callback_success` / `callback_failure`（需要时置于 Flask
   应用上下文中）。
3. 在 XXL-JOB Admin 将该任务的**任务超时时间**（秒）调到大于 worker 最长耗时。
   若 Admin 出现「任务结果丢失，标记失败」，说明最终回调过晚或未发出——请调大
   Admin 超时，并确认 worker 侧回调成功（`CallResult.success`）。

## 职责边界

超出 Admin HTTP 客户端有限重试之外的可靠投递，由宿主应用自行负责。Flask-XXLJob
**不提供**回调 Outbox、持久化队列或后台无限重试。若 `callback_*` 失败，请检查
`CallResult`，并在你自己的任务/worker 层重试或落库。

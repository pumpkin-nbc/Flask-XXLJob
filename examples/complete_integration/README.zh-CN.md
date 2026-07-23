[English](README.md) | [简体中文](README.zh-CN.md)

# 完整 Flask 接入案例

该案例采用适合实际项目的 Flask Application Factory 结构，覆盖执行器配置、
XXL-JOB 五个执行器端点、任务提交、取消、日志分页以及最终任务结果回调。

Flask-XXLJob 只负责协议适配。案例中的 `TaskGateway` 是业务适配层占位实现，请替换为
Celery、消息队列、RPC 或现有任务服务客户端。案例不会创建执行线程池，也不会在
`/run` 请求中执行耗时业务任务。

## 调用流程

```text
XXL-JOB Admin
    -> POST /xxl-job/run
    -> Flask-XXLJob 校验并解析 TriggerParam
    -> handle_run 把完整 TriggerRequest 提交给业务任务服务
    -> 业务任务异步完成
    -> POST /internal/task-result 回传到 Flask
    -> callback_success/callback_failure
    -> XXL-JOB Admin /api/callback
```

业务任务服务必须保存调度请求中的 `logId` 与 `logDateTime`，最终回传时保持不变。

## 安装与运行

在仓库根目录安装：

```bash
python -m pip install -e .
```

PowerShell：

```powershell
$env:XXL_JOB_ACCESS_TOKEN = "替换为Admin-Token"
$env:INTERNAL_RESULT_TOKEN = "替换为内部接口Token"
$env:XXL_JOB_AUTO_REGISTER = "false"
flask --app "examples.complete_integration.app:create_app" run --host 0.0.0.0 --port 5001
```

Bash：

```bash
export XXL_JOB_ACCESS_TOKEN="替换为Admin-Token"
export INTERNAL_RESULT_TOKEN="替换为内部接口Token"
export XXL_JOB_AUTO_REGISTER=false
flask --app 'examples.complete_integration.app:create_app' run --host 0.0.0.0 --port 5001
```

生产环境请使用正式 WSGI Server，不要使用 Flask 开发服务器。

## 环境变量

| 变量 | 示例/默认值 | 用途 |
| --- | --- | --- |
| `XXL_JOB_ADMIN_ADDRESSES` | `http://127.0.0.1:8080/xxl-job-admin` | Admin 基础地址，多个地址用逗号分隔。 |
| `XXL_JOB_ACCESS_TOKEN` | 空 | 必须与 Admin Access Token 一致。 |
| `XXL_JOB_EXECUTOR_APP_NAME` | `complete-flask-executor` | XXL-JOB 中配置的执行器 AppName。 |
| `XXL_JOB_EXECUTOR_ADDRESS` | `http://127.0.0.1:5001/xxl-job` | Admin 访问执行器的地址，包含路由前缀。 |
| `XXL_JOB_ROUTE_PREFIX` | `/xxl-job` | `/beat`、`/run`、`/idleBeat`、`/kill`、`/log` 的挂载前缀。 |
| `XXL_JOB_AUTO_REGISTER` | `false` | Admin 与外部执行器地址可达后设置为 `true`。 |
| `INTERNAL_RESULT_TOKEN` | 空 | 内部结果接口要求的 `X-Internal-Token`。 |

修改 `XXL_JOB_ROUTE_PREFIX` 时，必须同步修改 `XXL_JOB_EXECUTOR_ADDRESS`，使其以相同前缀结尾。

## 配置 XXL-JOB Admin

1. 新建或选择 AppName 为 `complete-flask-executor` 的执行器。
2. 设置 `XXL_JOB_AUTO_REGISTER=true` 使用自动注册；或者手动填写执行器地址
   `http://<flask-host>:5001/xxl-job`。
3. 在 Admin 配置 Access Token，并将相同值写入 `XXL_JOB_ACCESS_TOKEN`。
4. 新建任务并选择 BEAN 运行模式。`executorHandler` 会传入 `TaskGateway.submit`，
   请在该适配层分发到对应业务任务。
5. 执行参数可填写普通文本或 JSON；使用 `trigger.parse_params()` 可自动解析合法 JSON。

## 本地协议验证

健康检查：

```bash
curl http://127.0.0.1:5001/healthz
```

执行器心跳：

```bash
curl -X POST http://127.0.0.1:5001/xxl-job/beat \
  -H 'XXL-JOB-ACCESS-TOKEN: 替换为Admin-Token' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

手动触发任务：

```bash
curl -X POST http://127.0.0.1:5001/xxl-job/run \
  -H 'XXL-JOB-ACCESS-TOKEN: 替换为Admin-Token' \
  -H 'Content-Type: application/json' \
  -d '{
    "jobId": 1,
    "executorHandler": "demoJobHandler",
    "executorParams": "{\"customerId\": 42}",
    "logId": 10001,
    "logDateTime": 1784736000000
  }'
```

模拟业务任务服务回传成功结果：

```bash
curl -X POST http://127.0.0.1:5001/internal/task-result \
  -H 'X-Internal-Token: 替换为内部接口Token' \
  -H 'Content-Type: application/json' \
  -d '{
    "logId": 10001,
    "logDateTime": 1784736000000,
    "success": true,
    "message": "执行完成"
  }'
```

最后一步需要 XXL-JOB Admin 可访问；Admin 不可用时，内部接口会返回 HTTP 502，
响应中包含分类后的回调错误。

## 生产改造清单

- 将 `TaskGateway` 的所有方法替换为真实任务服务和日志服务调用。
- 如果业务不能接受回调丢失，请由业务系统持久化最终结果并保证可靠投递；
  Flask-XXLJob 本身不提供回调发件箱。
- 仅在内网开放 `/internal/task-result`；如已有服务认证机制，请替换示例 Token。
- 使用 HTTPS，并配置连接/读取超时与有界重试策略。
- 将执行器地址改为反向代理对外可访问的 URL。
- 在应用上下文之外调用回调辅助方法时显式传入 `app=`；同一扩展实例初始化多个应用时尤其如此。

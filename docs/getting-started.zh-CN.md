[English](getting-started.md) | [简体中文](getting-started.zh-CN.md)

# Python 入门者指南：运行第一个 Flask 执行器

本教程假设你只了解 Python 基础，还没有使用过 Flask 或 XXL-JOB。请按顺序操作：
先在本机跑通，再连接 XXL-JOB Admin，不要一开始就配置所有高级功能。

## 1. 先理解三个角色

- **XXL-JOB Admin**：定时调度任务，并发出 HTTP 请求。
- **Flask-XXLJob**：把 XXL-JOB 请求转换成普通 Python 函数调用。
- **你编写的函数**：提交或处理业务任务，然后返回协议响应。

Flask-XXLJob 不会替你创建任务队列，也不会自动执行后台任务。入门案例只打印收到的
参数，目的是先让你看懂数据如何从 XXL-JOB 进入 Python。

## 2. 检查 Python 并安装

需要 Python 3.8 或更高版本：

```bash
python --version
python -m pip install Flask-XXLJob
```

新项目建议使用虚拟环境：

```bash
python -m venv .venv
# Windows：.venv\Scripts\activate
# macOS/Linux：source .venv/bin/activate
python -m pip install Flask-XXLJob
```

仓库中已经准备好可以直接运行的文件：
[`examples/beginner/app.py`](../examples/beginner/app.py)。

## 3. 暂时不连接 Admin，在本地启动

入门文件特意设置了 `XXL_JOB_AUTO_REGISTER=False`。因此即使没有安装 XXL-JOB Admin，
也能先验证 Flask 和执行器接口是否正常。

PowerShell：

```powershell
python examples\beginner\app.py
```

macOS/Linux：

```bash
python examples/beginner/app.py
```

浏览器打开 <http://127.0.0.1:5001/>。看到 JSON 响应就表示 Flask 已经启动。

## 4. 发送第一个测试任务

PowerShell：

```powershell
$body = @{
    jobId = 1
    executorHandler = "demoJobHandler"
    executorParams = '{"name":"beginner"}'
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:5001/xxl-job/run" `
    -ContentType "application/json" `
    -Body $body
```

macOS/Linux：

```bash
curl -X POST http://127.0.0.1:5001/xxl-job/run \
  -H 'Content-Type: application/json' \
  -d '{"jobId":1,"executorHandler":"demoJobHandler","executorParams":"{\"name\":\"beginner\"}"}'
```

响应中应该出现 `code: 200`，运行 Flask 的终端会打印任务 ID、Handler 和解析后的参数。
完成这一步，就说明包已经能正常使用；此时还没有连接 Admin。

## 5. 看懂示例中的关键代码

- `Flask(__name__)`：创建 Flask Web 应用。
- `FlaskXXLJob(app)`：给 Flask 添加五个 XXL-JOB 执行器接口。
- `XXL_JOB_ROUTE_PREFIX="/xxl-job"`：接口统一放在 `/xxl-job` 路径下。
- `@xxl_job.on_run("demoJobHandler")`：把这个 JobHandler 精确绑定到该函数。
- `request.parse_params()`：如果执行参数是 JSON，则转换为 Python 对象。
- `XXLJobResponse.success()`：告诉 Admin 本次触发请求已经被接受。

这里返回成功只表示“任务触发已被接受”，不一定代表业务任务已经最终完成。

## 6. 再连接 XXL-JOB Admin

本地测试成功后，把 `app.py` 中的本地配置替换为：

```python
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
    XXL_JOB_ACCESS_TOKEN="",  # 与 Admin 保持一致
    XXL_JOB_EXECUTOR_APP_NAME="beginner-flask-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001/xxl-job",
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
    XXL_JOB_AUTO_REGISTER=True,
)
```

然后按以下步骤操作：

1. 启动 XXL-JOB Admin。
2. 在 Admin 新建 AppName 为 `beginner-flask-executor` 的执行器。
3. 确认 Admin 能访问 `XXL_JOB_EXECUTOR_ADDRESS`。如果使用 Docker 或不同电脑，
   `127.0.0.1` 通常是错误的，请填写 Flask 所在机器可被访问的 IP。
4. 重启 Flask，在 Admin 的执行器注册页面查看在线地址。
5. 新建 BEAN 模式任务，把 JobHandler 填为完全一致的 `demoJobHandler`。它必须与
   装饰器字符串一致，包括大小写；未知名称会在进入你的函数前被自动拒绝。

如果 Admin 配置了 Access Token，Flask 必须填写完全相同的值。手工测试接口时还要增加
`XXL-JOB-ACCESS-TOKEN` 请求头。

## 7. 业务任务完成后回调

真实异步任务需要保存触发请求中的 `log_id` 与 `log_date_time`。任务执行完成后调用：

```python
xxl_job.callback_success(
    app=app,
    log_id=log_id,
    log_date_time=log_date_time,
    message="执行完成",
)

# 执行失败时改用 callback_failure(...)
```

[完整接入案例](../examples/complete_integration/README.zh-CN.md)展示了业务任务服务如何通过
一个带鉴权的 Flask 接口回传结果。

## 常见问题

| 现象 | 常见原因 | 解决办法 |
| --- | --- | --- |
| Flask 无法启动 | 开启了自动注册，但没有填写地址 | 本地阶段保持 `XXL_JOB_AUTO_REGISTER=False`。 |
| 请求 `/run` 返回 404 | 使用了错误的路由前缀 | 入门案例应请求 `/xxl-job/run`。 |
| `/run` 返回 `Unsupported JobHandler` | Admin 名称与装饰器不完全一致 | 两处使用相同且区分大小写的名称，例如 `demoJobHandler`。 |
| 返回 Access Token 错误 | Flask 与 Admin Token 不一致 | 两边配置完全相同的 Token。 |
| Admin 找不到执行器 | Admin 无法访问执行器地址 | 跨容器或跨机器时不要使用 `127.0.0.1`。 |
| `/run` 成功但业务没有执行 | 入门案例只打印/提交任务 | 将 `handle_run` 替换为你的业务任务提交逻辑。 |
| Admin 没有最终状态 | 触发成功不等于最终回调 | 任务完成后调用 `callback_success` 或 `callback_failure`。 |

下一步只需按实际需要阅读[配置参考](configuration.zh-CN.md)，不必在开始前理解全部配置项。

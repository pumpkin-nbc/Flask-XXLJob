[English](migration.md) | [简体中文](migration.zh-CN.md)

# 从 Java 中转迁移

以前，Python 任务需要经过 Java 执行器服务：

```text
XXL-JOB -> Java executor -> Java calls Python HTTP -> Python runs task
```

使用 Flask-XXLJob 后，Flask 项目直接作为执行器：

```text
XXL-JOB -> Flask (Flask-XXLJob) -> your on_run submits the task
```

## 步骤

1. 将 `Flask-XXLJob` 加入依赖，并在工厂函数中初始化扩展。
2. 将 `XXL_JOB_EXECUTOR_ADDRESS` 指向 Flask 服务，并沿用与 Java 执行器相同的 `XXL_JOB_ACCESS_TOKEN`。
3. 把原本在 Java 层提交任务的逻辑迁移到 `on_run` 处理函数中，调用你现有的任务服务。
4. 用任务工作端的 `callback_success` / `callback_failure` 调用替换 Java 侧的最终状态更新。
5. 使用相同的应用名称注册执行器，使现有任务绑定继续有效。

## 说明

任务路由、阻塞策略、超时与重试仍由 XXL-JOB Admin 管理。Flask-XXLJob 只负责协议中转；你的任务服务始终完全掌控执行过程。

## 从 0.3.4 升级到 0.4.0

`0.4.0` 将以 Registry Thread 为中心的生命周期替换为进程级状态机。任务调度、五个
执行器端点、Callback、Admin 协议与 `REGISTRY_INTERVAL` 都没有变化。

```bash
pip install --upgrade flask-xxljob==0.4.0
```

尚未正式发布的 `XXL_JOB_AUTO_REGISTER_ON_INIT` 已直接删除，不提供弃用兼容期。只要
该键仍在 `app.config`，即使 `XXL_JOB_ENABLED=False`，`init_app()` 也会同步失败：

- 旧值为严格 `False`：改用 `XXL_JOB_AUTO_REGISTER=False`，并在需要的位置显式调用
  `start_registry(app)`。
- 旧值为严格 `True`：删除该键，保留 `XXL_JOB_AUTO_REGISTER=True`。
- 其他旧值：删除该键，统一使用 `XXL_JOB_AUTO_REGISTER`。

唯一自动启动条件现在是 `XXL_JOB_ENABLED and XXL_JOB_AUTO_REGISTER`。Gunicorn
preload 或 Application Factory 同时被 Celery 导入时使用：

```python
app.config["XXL_JOB_AUTO_REGISTER"] = False
xxl_job.init_app(app)
xxl_job.start_registry(app)  # fork 后在拥有 Registry 的进程中执行
```

`XXL_JOB_DEREGISTER_ON_EXIT` 现在默认 `False`。`stop_registry()` 也默认只做本地
立即停止并保留 `registered`。需要为当前清理责任申请后台注销时使用
`stop_registry(remove=True)`；需要确定性结果时，本地停止后同步调用
`remove_executor()`。成功的终止 Remove 会被 finalizer 复用；如果同 generation
后来又有 accepted register 重新建立远端身份，就会产生新的必要清理责任，而不是对
失败 Remove 的重试。

完整 Registry 配置仅在 enabled 状态真正请求 Registry 操作时校验，因此
`AUTO_REGISTER=False` 可在没有 Admin 配置时完成纯协议初始化。`ENABLED=False` 会
短路 Registry 行为，但已删除配置检测与现有字段校验仍然执行。

fork 子进程会在读取本地状态前替换全部 Registry 锁、Worker、generation、Remove、
sequence 与快照。同一进程内四类 Registry RPC 严格串行。本版本没有增加跨进程锁、
Leader 选举、信号处理或部署检测；每个启动 Registry 的 Worker 仍拥有自己的
lifecycle。

## 从 0.3.3 升级到 0.3.4

`0.3.4` 仅根据配置（`XXL_JOB_ENABLED` + `XXL_JOB_AUTO_REGISTER`）启动自动注册，
不再参考 `app.debug` 或 `WERKZEUG_RUN_MAIN`，因此 Gunicorn 等在 `DEBUG=True`
下也会正常注册。

```bash
pip install --upgrade flask-xxljob==0.3.4
```

## 从 0.3.2 升级到 0.3.3

`0.3.3` 允许成功响应携带可选消息，`msg` 为第一个参数：

```python
return XXLJobResponse.success("job queued")
return XXLJobResponse.success(msg="job queued", content="accepted")
```

```bash
pip install --upgrade flask-xxljob==0.3.3
```

## 从 0.3.1 升级到 0.3.2

`0.3.2` 会在加载配置时始终把 `XXL_JOB_ROUTE_PREFIX` 附加到
`XXL_JOB_EXECUTOR_ADDRESS`。执行器地址只需填写服务基础地址：

```python
app.config.update(
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
)
# 注册地址变为 http://127.0.0.1:5001/xxl-job
```

请勿在 `XXL_JOB_EXECUTOR_ADDRESS` 中再手写路由前缀；例如地址写成
`http://127.0.0.1:5001/xxl-job` 且前缀为 `/xxl-job` 时，结果会变成
`http://127.0.0.1:5001/xxl-job/xxl-job`。

```bash
pip install --upgrade flask-xxljob==0.3.2
```

## 从 0.3.0 升级到 0.3.1

`0.3.1` 只调整发行元数据与发布配置。发行包名称改为规范化的小写形式，公开 Python
导入路径与运行时 API 均不变。

```bash
pip install --upgrade flask-xxljob==0.3.1
```

## 从 0.2.1 升级到 0.3.0

0.3.0 将 Run 注册改为显式 JobHandler 分发。请把：

```python
@xxl_job.on_run
def handle_run(request):
    ...
```

改为一个或多个命名 Handler：

```python
@xxl_job.on_run("demoJobHandler")
def handle_demo(request):
    ...

@xxl_job.on_run("reportJobHandler")
def handle_report(request):
    ...
```

Admin 中的 JobHandler 必须完全一致，包括大小写；不再提供无名称兜底。应用级调用改为
`set_run_callback(app, "名称", func)`、`get_run_callback(app, "名称")` 和
`register_callbacks(app, run={"名称": func})`。

0.3.0 还消除了 Flask 应用上下文之外含糊的应用选择。若扩展实例恰好初始化了一个应用，辅助方法仍可省略 `app`；一旦初始化了多个应用，在上下文之外调用回调、注册、状态与注册服务生命周期辅助方法时必须显式传入 `app`。应用上下文内的调用方式不变。

初始化前注册的 `on_*` 装饰器仍会注入其后初始化的每个应用，公共导入路径也保持不变。包元数据、`__version__` 与 CLI 现统一读取同一个内部版本源。

### 升级

```bash
pip install --upgrade flask-xxljob==0.3.0
```

### 回滚

```bash
pip install flask-xxljob==0.2.1
```

## 从 0.2.0 升级到 0.2.1

0.2.1 是稳定性版本。协议字符串字段现会拒绝非字符串值；执行器 `POST` 路由冲突会在初始化阶段、应用出现部分配置之前失败；注册服务停止超时时，会在正在进行的续约返回后完成已请求的注销。只含空白的 Access Token 会被视为空 Token；Admin 与执行器 URL 会严格校验方案、主机和端口，同时仍支持上下文路径。

现有合法请求与配置无需修改。如果应用代码在构造 `TriggerRequest`、`CallbackRequest` 或 `RegistryRequest` 时给字符串字段传入整数、布尔、数组或对象，请在升级前显式转换为字符串。

### 升级

```bash
pip install --upgrade flask-xxljob==0.2.1
```

### 回滚

```bash
pip install flask-xxljob==0.2.0
```

## 从 0.1.2 升级到 0.2.0

0.2.0 是向下兼容的次要版本。它新增了应用级请求处理函数注册、批量回调、可配置的同步 Admin 重试/故障转移策略、插件状态查询与 `xxljob status` CLI 命令、更丰富的 `CallResult` 字段、常量时间 Token 比较，以及公共异常层级。0.1.2 的全部公共 API、导入路径与配置项均保持不变。

### 我需要修改代码或配置吗？

不需要。所有新功能均为可选启用，新配置项的默认值与 0.1.2 行为一致：

- 应用级注册：`register_callbacks`、`set_*_callback(replace=...)`、`get_*_callback`。`on_*` 装饰器仍然可用。
- 批量回调：`callback_many(...)`。单条 `callback*` 方法保持不变。
- Admin 调用策略（默认保持 0.1.2 行为）：`XXL_JOB_ADMIN_RETRY_COUNT`（0）、`XXL_JOB_ADMIN_RETRY_BACKOFF`（0.0）、`XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR`（True）、`XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON`（False）、`XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR`（False）、`XXL_JOB_CALLBACK_BATCH_MAX_SIZE`（100）。
- 状态：`get_status(app=None)` 返回 `XXLJobStatus`；`start_registry` / `stop_registry` 控制注册线程。
- 异常：`FlaskXXLJobError` 为新的基类；所有旧名称保留为别名，因此现有的 `except XXLJobError` / `except XXLJobConfigError` 继续有效。

### 升级

```bash
pip install --upgrade flask-xxljob==0.2.0
```

### 回滚

```bash
pip install flask-xxljob==0.1.2
```

## 从 0.1.1 升级到 0.1.2

0.1.2 是向下兼容的补丁版本，重点在于协议复核、注册与回调可靠性、更清晰的配置校验，以及更完善的测试和中英文文档。没有破坏性 API 变更，0.1.1 的使用方式继续有效。

### 我需要修改代码或配置吗？

不需要。0.1.1 的全部公共 API、导入路径与配置项均保持不变。唯一的新增变化是 `register_executor`、`remove_executor` 与 `callback*` 方法返回的调用结果上新增了可选的 `error_type` 分类，用于在不检查底层 `requests` 对象的情况下区分失败原因（`network`、`timeout`、`http`、`invalid_json`、`business`、`config`）。是否读取它完全可选。

### 升级

```bash
pip install --upgrade flask-xxljob==0.1.2
```

### 验证

1. 检查已安装版本：`python -c "import flask_xxljob; print(flask_xxljob.__version__)"` 输出 `0.1.2`。
2. 启动你的 Flask 服务（或 `examples/` 中的示例）。
3. 确认 `POST /beat` 返回 `{"code": 200, ...}`。
4. 确认执行器完成注册（在 Admin 的在线机器列表查看，或调用 `register_executor`）。
5. 确认 `POST /run` 能进入你的 `on_run` 处理函数。
6. 确认任务完成后调用 `callback_success` / `callback_failure`。

### 回滚

```bash
pip install flask-xxljob==0.1.1
```

实际业务任务仍由你的 Flask 项目执行；Flask-XXLJob 从不自行运行任务。

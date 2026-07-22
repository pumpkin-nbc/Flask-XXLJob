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
pip install --upgrade Flask-XXLJob==0.2.0
```

### 回滚

```bash
pip install Flask-XXLJob==0.1.2
```

## 从 0.1.1 升级到 0.1.2

0.1.2 是向下兼容的补丁版本，重点在于协议复核、注册与回调可靠性、更清晰的配置校验，以及更完善的测试和中英文文档。没有破坏性 API 变更，0.1.1 的使用方式继续有效。

### 我需要修改代码或配置吗？

不需要。0.1.1 的全部公共 API、导入路径与配置项均保持不变。唯一的新增变化是 `register_executor`、`remove_executor` 与 `callback*` 方法返回的调用结果上新增了可选的 `error_type` 分类，用于在不检查底层 `requests` 对象的情况下区分失败原因（`network`、`timeout`、`http`、`invalid_json`、`business`、`config`）。是否读取它完全可选。

### 升级

```bash
pip install --upgrade Flask-XXLJob==0.1.2
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
pip install Flask-XXLJob==0.1.1
```

实际业务任务仍由你的 Flask 项目执行；Flask-XXLJob 从不自行运行任务。

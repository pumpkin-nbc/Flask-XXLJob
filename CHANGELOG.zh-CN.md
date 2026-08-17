[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并遵循 [语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

## [0.4.0] - 2026-08-16

### 变更

- 将 PID 隔离、lifecycle generation、当前/停止中 Worker ownership、Pending/Active
  Remove、cleanup 调度、RPC 顺序及日志最终关闭统一收口到 `RegistryService`。
- 自动启动只保留 `XXL_JOB_ENABLED && XXL_JOB_AUTO_REGISTER` 一个条件，并统一调用
  公开 `start_registry()` 路径。
- `stop_registry(remove=False)` 变成默认：立即分离并唤醒本地续约，不 join、不访问
  Admin，也不修改最近 `registered` 快照。`remove=True` 为该 generation 排队一次
  后台 Remove。
- 当前进程全部真实 Registry RPC 共用一个网络锁；completion 通过严格递增 sequence
  提交，旧成功或失败都不能晚写覆盖更新状态。
- PID 变化会在接触继承的 Lock、Thread 或 Event 前只替换空白 Registry 进程状态；
  应用 Runtime、Handler、Callback、路由、配置与无进程资源的 AdminClient 保持不变。
- Runtime finalizer 始终非阻塞；退出注销复用 generation 资格和统一 Scheduler，托管
  日志在全部后台收尾空闲后恰好关闭一次。
- 构建后端继续限制在 Hatchling 1.32 以下，使当前 Twine 可以校验 Core Metadata 2.4。

### 配置

- 删除尚未发布的 `XXL_JOB_AUTO_REGISTER_ON_INIT`。只要该键存在就同步抛迁移错误，
  即使扩展 disabled 也不会静默忽略。
- `XXL_JOB_DEREGISTER_ON_EXIT` 默认值改为 `False`，避免单个 Worker 自动删除共享
  执行器身份。
- 将初始化字段校验与完整 Registry 配置校验分离。`AUTO_REGISTER=False` 可以在没有
  Admin Registry 配置时初始化 HTTP 协议；enabled Registry 操作在线程/RPC 前校验。
- `XXL_JOB_ENABLED=False` 会短路 Registry 行为；同步单次 API 返回安全的本地
  disabled `CallResult`，不分配 RPC sequence，也不改变 lifecycle 状态。

### 兼容性

- 任务协议、Handler 与 Callback API、五个执行器端点、Admin Registry 协议、续约
  间隔、`XXLJobStatus` 字段、公开导入、Python 3.8-3.14 与 Flask 1.x-3.x 不变。
- 多 Worker 拓扑仍是每进程一个 Registry Worker；未增加 Leader 选举、跨进程锁、
  信号处理或部署检测。

### 测试

- 最终本地测试为 454 项通过、2 项可选官方 Admin 测试跳过，行覆盖率 93.72%。覆盖
  PID/disabled 顺序、generation ownership、Remove 竞态、cleanup 启动失败、严格
  completion sequence、非阻塞 finalizer 与日志恰好关闭一次。

## [0.3.4] - 2026-07-25

### 变更

- `init_app()` 阶段的自动注册现在只依赖 `XXL_JOB_ENABLED` 与
  `XXL_JOB_AUTO_REGISTER`，不再检查 `app.debug` 或 `WERKZEUG_RUN_MAIN`，因此
  Gunicorn（等）在 `DEBUG=True` 下也会启动注册线程。

## [0.3.3] - 2026-07-24

### 新增

- `XXLJobResponse.success()` 新增可选 `msg` 作为第一个参数，对应官方
  `ReturnT.msg`；`content` 为第二个参数，`msg` 默认仍为 `None`。

### 文档

- 补充长任务 / Celery 回调流程、Admin「任务结果丢失，标记失败」与超时配置说明，
  并明确回调 Outbox / 持久化重试不属于本插件职责。

## [0.3.2] - 2026-07-23

### 变更

- `XXL_JOB_EXECUTOR_ADDRESS` 现在只需填写服务基础地址。加载配置时会始终附加
  `XXL_JOB_ROUTE_PREFIX`，使 Admin 注册地址与执行器接口路径一致。

## [0.3.1] - 2026-07-23

### 变更

- 发行包元数据名称改为规范化的小写形式 `flask-xxljob`。它与
  `Flask-XXLJob` 仍是同一个 PyPI 项目，Python 导入包仍为 `flask_xxljob`。
- TestPyPI 已发布 `0.3.0` 后，将 Trusted Publishing 工作流和发布文档更新为
  发布 `v0.3.1`。

## [0.3.0] - 2026-07-23

### 新增

- 新增只使用标准库、按应用隔离的 Flask-XXLJob 托管日志。托管日志默认关闭，轮转文件
  与控制台目标可单独开启或同时开启。
- 开启托管日志时默认启用控制台日志，并使用一个控制台 Handler 同时输出正常与异常
  记录；新增共用等级与格式校验、敏感信息过滤、生命周期清理，以及
  `XXLJobStatus` 和 `xxljob status` 中的日志状态字段。
- 托管控制台记录现按等级着色：`DEBUG` 蓝色、`INFO` 绿色、`WARNING` 黄色、
  `ERROR` 红色、`CRITICAL` 加粗红色；文件日志不包含 ANSI 转义码。

### 变更

- `/run` 现通过 `@xxl_job.on_run("名称")` 按 `executorHandler` 精确、区分大小写地
  自动分发，支持注册多个命名 Handler；移除裸装饰器与无名称兜底。应用级 Run API
  统一为 `set_run_callback(app, name, func)`、`get_run_callback(app, name)` 与映射式
  `register_callbacks(run={name: func})`，并提供批量原子校验。
- Flask 应用上下文之外的应用解析不再含糊：恰好初始化一个应用时仍可省略 `app`；同一扩展初始化多个应用后则必须显式传入 `app`。初始化前注册的 `on_*` 装饰器仍会注入其后初始化的每个应用。
- 包元数据、`flask_xxljob.__version__` 与 CLI 现统一使用 `flask_xxljob/_version.py` 作为唯一版本源。
- 路由冲突检查、应用解析和生命周期协调已拆分为内部辅助模块，公共导入路径不变。

### 文档

- 更新双语 README、API 参考与迁移指南，说明严格字符串校验、路由冲突检测、延迟注销与多应用迁移方式。
- 新增双语日志与部署说明，包括容器仅控制台方案和 `RotatingFileHandler` 的多进程限制。
- 新增经过测试的中英文端到端 Flask 接入案例，覆盖 Application Factory、全部执行器回调、环境变量配置和最终任务结果上报。
- 将主快速入门改为面向 Python 初学者、可先在本地直接运行的渐进式教程，补充单文件案例、PowerShell/Bash 请求、Admin 接入步骤与故障排查。

## [0.2.1] - 2026-07-22

### 修复

- Trigger、Callback 与 Registry 的字符串字段现只接受字符串；字段缺失或为 `None` 时仍使用文档默认值。非法执行器请求返回 XXL-JOB `code=500` 响应；非法出站回调会在发送任何 HTTP 请求前抛出 `XXLJobValidationError`。
- 初始化现会在注册 CLI、Blueprint、扩展状态或注册线程之前拒绝有冲突的执行器 `POST` 路径；同路径 `GET` 路由仍然有效。
- 注册服务停止被正在进行的续约阻塞而超时时，工作线程会在续约完成后串行且最多一次地执行已请求的注销。
- 只含空白的 Access Token 会被规范化为空；Admin 与执行器 URL 使用标准 URL 解析严格校验 `http`/`https` 方案、主机与合法端口，同时保留上下文路径。

### 测试

- 新增严格模型校验、路由冲突与延迟注销回归测试。CI 现要求 Python 3.12/Flask 3 覆盖率至少 90%，并检查文档、wheel/sdist 内容、元数据以及安装后 CLI 冒烟。

## [0.2.0] - 2026-07-22

### 修复

- Admin 返回非对象 JSON 时现归类为 `invalid_json`，不再抛出 `AttributeError`。
- 执行器请求体现在按严格内存上限读取，`/` 会规范化为根路由前缀，执行器路由错误也不再覆盖宿主应用自定义的 404/405 处理器。
- 执行器路由改用兼容 Flask 1.x 的 `route(..., methods=["POST"])` API，不再使用 Flask 2.0 才提供的 `post()` 快捷方法。
- 注册服务停止时不再与尚未结束的续约并发注销，避免旧续约在注销后重新注册执行器。

### 新增

- 应用级请求处理函数注册：`register_callbacks(app=None, *, run=..., idle_beat=..., kill=..., log=..., replace=False)`、`set_run_callback`/`set_idle_beat_callback`/`set_kill_callback`/`set_log_callback`（支持 `replace`），以及 `get_run_callback`/`get_idle_beat_callback`/`get_kill_callback`/`get_log_callback`。`on_*` 装饰器仍作为默认模板可用。解析优先级为：先应用级注册表，再扩展级默认。
- 批量回调：`callback_many(callbacks, app=None)` 在一次官方请求中发送多条 `HandleCallbackParam`。发送前完整校验每一条，绝不自动拆分；任一非法或超过 `XXL_JOB_CALLBACK_BATCH_MAX_SIZE` 都整体拒绝且不发送任何数据。
- 可配置、有限的同步 Admin 调用策略：`XXL_JOB_ADMIN_RETRY_COUNT`、`XXL_JOB_ADMIN_RETRY_BACKOFF`、`XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR`、`XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON`、`XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR`。重试与退避均有上限；不引入后台线程或持久化。
- `CallResult`/`AdminCallResult` 新增可选字段 `attempt_count`、`elapsed_ms`、`http_status`（均有默认值）。
- 插件状态查询：`XXLJobStatus` 模型，以及 `get_status(app=None)`、`start_registry(app=None)`/`stop_registry(app=None)` 生命周期控制。状态只描述插件本身（绝不含 Token 或业务任务状态）。
- CLI `xxljob status` 命令（Flask 分组与独立脚本），输出人类可读且不含 Token，最近一次注册失败时以非零码退出。
- 公共异常层级以 `FlaskXXLJobError` 为根，新增 `XXLJobInitializationError`、`XXLJobCallbackRegistrationError`、`XXLJobValidationError`、`XXLJobAdminCallError`（及既有子类）。所有旧名称保留为别名（`XXLJobError`、`XXLJobConfigError`、`XXLJobRequestError` 等）。
- 新增 `docs/api-reference` 与 `docs/integration-testing` 文档、`tox.ini` 与 GitHub Actions 矩阵、可选开启的官方 XXL-JOB 2.4.1 集成测试（由 `XXLJOB_ADMIN_URL` 控制），以及三个新示例：`batch_callback`、`multiple_apps`、`registry_status`。

### 变更

- 在首次发布到 PyPI 前，项目许可证由 MIT 调整为 Apache-2.0；包元数据中的作者改为 Pumpkin，并指向 `pumpkin-nbc/Flask-XXLJob` 仓库。
- Access Token 比较改用 `hmac.compare_digest` 以实现常量时间比较，并安全拒绝缺失/非字符串请求头。空 Token 的官方模式保持不变；Token 绝不写入日志或返回。
- 当显式提供 Admin 调用策略时（内置客户端现已如此），默认故障转移行为为：网络/超时始终转移；HTTP 错误转移；非法 JSON 与业务失败不转移。未提供策略的 `post_to_admins` 直接调用者仍保持与 0.1.2 完全一致的行为。

### 安全

- 常量时间 Token 比较降低时序侧信道风险。请求体大小（字节）与 `executorParams` 长度（字符）限制仍返回 XXL-JOB JSON 错误，绝不返回 HTML。

### 测试

- 新增应用级注册（优先级、多应用隔离、重复/`replace`、工厂注入、处理函数异常/错误返回）、批量回调（空/超限/非法条目/中文/截断/故障转移/不部分发送）、重试策略（重试、耗尽、故障转移、上限、Token 不泄露、新字段）、状态/生命周期与 CLI status，以及 Token 与请求限制安全的测试。
- 新增非对象 Admin JSON、有界请求流读取、宿主错误处理器保留、根前缀规范化与慢注册线程停止的回归测试；制品检查现在还会验证许可证元数据与法律文件，Flask 1.x 测试环境也会固定兼容的 MarkupSafe 版本。

### 文档

- 新增“0.1.2 到 0.2.0”迁移章节、API 参考与集成测试指南、兼容性矩阵说明，并刷新双语的配置/回调/请求处理函数文档与 README。

升级说明：这是一个向后兼容的次要版本。使用以下命令升级：

```bash
pip install --upgrade flask-xxljob==0.2.0
```

无需修改任何代码或配置。所有新行为均通过新 API 与新配置项选择性启用，其默认值与 0.1.2 一致。

## [0.1.2] - 2026-07-22

### 修复

- 加载配置时对 Admin 与执行器地址进行规范化：去除首尾空格与多余的尾部斜杠，同时保留上下文路径（例如 `/xxl-job-admin`）与地址顺序。无论地址书写方式如何，注册、注销与回调 URL 都保持一致。

### 调整

- `register_executor`、`remove_executor` 与 `callback*` 方法返回的结果新增可选的 `error_type` 分类（`network`、`timeout`、`http`、`invalid_json`、`business`、`config`，成功时为 `None`），无需检查底层 `requests` 对象即可区分失败原因。现有 `CallResult`/`AdminCallResult` 字段保持不变，且任何结果中都不包含 Access Token。
- 配置校验错误信息现在统一包含配置项名称、收到的值类型（非敏感字段包含值）以及期望格式。

### 测试

- 新增针对调用结果错误分类（注册与回调：网络、超时、HTTP、非法 JSON、业务失败、无 Admin）、Admin/执行器地址规范化、路由前缀变体（空、前导/尾部/重复斜杠）以及 `Content-Type: application/json; charset=UTF-8` 解析（含中文 `executorParams`）的测试。

### 文档

- 新增 “从 0.1.1 升级到 0.1.2” 的升级与回滚指南，更新中英文文档与版本引用，并记录 `error_type` 结果字段。

升级说明：这是一个向下兼容的补丁版本。使用以下命令升级：

```bash
pip install --upgrade flask-xxljob==0.1.2
```

无需修改代码或配置；唯一的新增是调用结果上的可选 `error_type` 字段。

## [0.1.1] - 2026-07-22

### 修复

- 现在支持在 `init_app` 之前进行模块级处理函数注册（导入阶段使用 `@xxl_job.on_run` 装饰器），不再因缺少应用上下文而抛异常。
- `_resolve_app` 改用 `flask.has_app_context()`，回调与注册辅助方法在应用上下文之外不再抛出难以理解的 `RuntimeError`。
- 执行器接口始终返回 XXL-JOB 标准 JSON。空请求体、非 JSON 内容以及 JSON 数组/标量现在返回明确的 `code: 500` 失败，而不是被静默当作 `{}`。
- 数字字段（`jobId`、`logId`、`logDateTime` 等）安全转换：缺失使用默认值，`0` 被保留，非数字值返回协议失败而不会崩溃。
- 执行器路由上的错误 HTTP 方法（405）返回 XXL-JOB JSON，而不是 Werkzeug 的 HTML 错误页；其他应用路由保持 Flask 默认行为。
- 任务结果回调在收到第一个有效的 Admin 业务响应后即停止，避免向多个 Admin 地址重复投递。

### 变更

- 重复注册处理函数现在抛出 `XXLJobError`，而不是静默覆盖之前的处理函数。
- 处理函数返回除 `XXLJobResponse`（`/log` 还包括 `LogResponse`）以外的类型时，返回明确的 “unsupported response type” 失败。
- 仅当启用 `XXL_JOB_AUTO_REGISTER` 时，配置校验才要求 Admin 地址、执行器名称与执行器地址，并校验 Admin/执行器地址使用 `http`/`https` 方案。
- `callback`、`callback_success`、`callback_failure` 接受 `message=None`，并校验 `log_id`/`log_date_time` 为整数（拒绝布尔值）。原有的 `handle_msg` 关键字用法保持兼容。
- 新增异常类型 `XXLJobConfigurationError`、`XXLJobRequestError`、`XXLJobProtocolError`、`XXLJobRegistryError`，以及带 `message`/`admin_address` 访问器的 `AdminCallResult` 别名。`XXLJobConfigError` 作为别名保留。

### 文档

- 更新中英文 README 与 `docs/` 文档，说明 init 前注册、重复注册行为、统一 JSON 错误响应、放宽的配置规则以及扩展后的结果/异常模型。

### 测试

- 新增针对注册模式、请求解析、处理函数返回类型、统一错误响应、配置校验、URL 拼接、回调校验以及多 Admin 故障转移语义的回归与协议测试。

升级说明：这是一个向下兼容的补丁版本。使用以下命令升级：

```bash
pip install --upgrade flask-xxljob==0.1.1
```

唯一需要注意的行为变更是：重复注册同一处理函数现在会抛出 `XXLJobError`，而不再静默覆盖之前的处理函数。

## [0.1.0] - 2026-07-21

### 新增

- 实现官方 XXL-JOB 2.4.1 执行器协议的 Flask 扩展。
- 支持 Application Factory，应用间 Runtime 隔离并保存在 `app.extensions["xxljob"]`。
- 执行器接口：`/beat`、`/idleBeat`、`/run`、`/kill`、`/log`。
- 请求处理函数注册：`on_run`、`on_idle_beat`、`on_kill`、`on_log`。
- 使用官方 `XXL-JOB-ACCESS-TOKEN` 请求头的 Access Token 校验。
- 执行器注册、注销与自动续约。
- 任务结果回调客户端：`callback`、`callback_success`、`callback_failure`。
- 多个 Admin 地址与故障转移。
- Flask CLI 分组 `xxljob` 及独立的 `flask-xxljob` 控制台脚本。
- 中英文双语文档。

[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并遵循 [语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

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
pip install --upgrade Flask-XXLJob==0.1.2
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
pip install --upgrade Flask-XXLJob==0.1.1
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

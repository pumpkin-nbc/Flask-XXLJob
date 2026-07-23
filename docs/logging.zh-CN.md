[English](logging.md) | [简体中文](logging.zh-CN.md)

# 日志

Flask-XXLJob 记录初始化、注册、续约、注销、Admin 故障转移、Callback 与协议失败等
插件诊断事件，不记录业务任务输出。托管日志默认关闭，不创建目录或文件，也不添加
控制台 Handler。

## 输出模式

仅文件（只设置 `XXL_JOB_LOG_ENABLED=True` 时也是此结果）：

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_ENABLED=False,
)
```

仅控制台：

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_STREAM="stderr",
)
```

文件与控制台同时输出：

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
)
```

两个目标都关闭或总开关关闭时，Flask-XXLJob 不修改 Runtime Logger 的等级和传播
设置。宿主可使用标准 Python Logging 在 `flask_xxljob` Logger 上添加 Handler。
包级 `NullHandler` 避免意外的默认输出，但不会阻止日志传播到宿主 Handler。

## 文件、格式与轮转

相对 `XXL_JOB_LOG_PATH` 按进程当前工作目录解析，`XXLJobStatus.log_file` 返回最终
绝对路径。文件与控制台共用 `XXL_JOB_LOG_LEVEL`、`XXL_JOB_LOG_FORMAT` 和
`XXL_JOB_LOG_DATE_FORMAT`。等级、编码、流、轮转值与格式均在 `init_app()` 时严格校验。

每个 Flask Runtime 拥有唯一的
`flask_xxljob.app.<应用名>.<序号>.<组件>` Logger 层级，同名 Flask 应用也相互隔离。
扩展从不修改根 Logger 或 `app.logger`，只移除自己标记的 Handler，并在应用回收或
解释器退出时自动清理。清理控制台 Handler 不会关闭 `sys.stdout` 或 `sys.stderr`。

存在托管目标时，默认 `XXL_JOB_LOG_PROPAGATE=False`，避免宿主重复输出。只有确实
需要托管与宿主 Handler 同时接收记录时才设置为 `True`。

## 敏感信息

插件事件只包含安全上下文、结果分类、HTTP 状态和异常类型，不包含请求体、请求头、
Access Token、`executorParams`、`glueSource`、`handleMsg` 或用户异常文本。每个托管
Handler 上还有最终脱敏 Filter，即使 `DEBUG` 等级也会替换已识别的凭据与私钥文本。

这是额外防线，不表示可以向插件 Logger 写入任意业务数据。业务日志请由应用单独配置。

## 容器与多进程

Docker、Kubernetes、Gunicorn、systemd 等环境建议：

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
    XXL_JOB_LOG_CONSOLE_STREAM="stdout",
)
```

由平台采集、保留、检索和轮转该输出流。Python 标准 `RotatingFileHandler` 不保证多个
工作进程共享同一文件时安全。多进程部署请使用控制台聚合、宿主管理的 Handler，或为
每个进程配置独立文件。

全部选项见[配置](configuration.zh-CN.md)。

[English](deployment.md) | [简体中文](deployment.zh-CN.md)

# 部署

## 执行器地址

将 `XXL_JOB_EXECUTOR_ADDRESS` 设置为 XXL-JOB Admin 能够访问的 URL。在容器化或多主机部署中，这通常是服务地址，而不是 `127.0.0.1`。

## 自动注册

当 `XXL_JOB_AUTO_REGISTER=True` 时，扩展会启动一个守护线程，注册执行器并每隔 `XXL_JOB_REGISTRY_INTERVAL` 秒续约一次。注册失败会记录日志，且绝不会导致应用崩溃。

## Flask debug reloader

在 Flask debug reloader 下，注册线程只在 reloader 子进程中启动（此时 `WERKZEUG_RUN_MAIN=true`），因此不会重复启动。

## 多进程

每个初始化扩展的工作进程都会使用相同的执行器应用名称与地址进行注册。由于注册键是地址，在同一地址后运行多个工作进程没有问题；使用不同地址运行的工作进程会注册为多个执行器实例。请据此规划你的进程模型。

容器中的插件诊断日志建议仅输出到控制台，由平台统一采集、保留与轮转：

```python
app.config.update(
    XXL_JOB_LOG_ENABLED=True,
    XXL_JOB_LOG_FILE_ENABLED=False,
    XXL_JOB_LOG_CONSOLE_ENABLED=True,
)
```

标准 `RotatingFileHandler` 只管理当前进程，不能保证 Gunicorn 等多个工作进程共享
同一文件时安全。请改用独立文件、宿主 Logging 或控制台聚合。详见[日志](logging.zh-CN.md)。

## 手动注册

你可以关闭自动注册，改为通过 CLI 注册：

```bash
flask --app "project:create_app" xxljob register
```

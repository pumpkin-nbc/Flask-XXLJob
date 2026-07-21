[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# 配置

所有配置都在 `init_app()` 阶段从 `app.config` 读取。扩展从不在模块导入阶段读取配置，也不在构造函数中访问 `current_app`。

## 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `XXL_JOB_ENABLED` | `True` | 是否启用扩展。 |
| `XXL_JOB_ADMIN_ADDRESSES` | `[]` | XXL-JOB Admin 基础地址列表。 |
| `XXL_JOB_ACCESS_TOKEN` | `""` | Access Token，空表示无 Token 模式。 |
| `XXL_JOB_EXECUTOR_APP_NAME` | `"flask-xxljob-executor"` | 执行器应用名称。 |
| `XXL_JOB_EXECUTOR_ADDRESS` | `""` | Admin 访问本执行器的地址。 |
| `XXL_JOB_ROUTE_PREFIX` | `""` | 执行器接口的 URL 前缀。 |
| `XXL_JOB_AUTO_REGISTER` | `True` | 是否启动自动注册续约。 |
| `XXL_JOB_REGISTRY_INTERVAL` | `30` | 注册续约间隔（秒）。 |
| `XXL_JOB_HTTP_CONNECT_TIMEOUT` | `3` | HTTP 连接超时（秒）。 |
| `XXL_JOB_HTTP_READ_TIMEOUT` | `5` | HTTP 读取超时（秒）。 |
| `XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH` | `10000` | `handleMsg` 最大长度。 |
| `XXL_JOB_MAX_REQUEST_SIZE` | `1048576` | 请求体最大字节数。 |
| `XXL_JOB_MAX_PARAM_LENGTH` | `65536` | `executorParams` 最大长度。 |

## 示例

```python
app.config.update(
    XXL_JOB_ADMIN_ADDRESSES=[
        "http://admin-1:8080/xxl-job-admin",
        "http://admin-2:8080/xxl-job-admin",
    ],
    XXL_JOB_ACCESS_TOKEN="",
    XXL_JOB_EXECUTOR_APP_NAME="project-executor",
    XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
    XXL_JOB_AUTO_REGISTER=True,
    XXL_JOB_REGISTRY_INTERVAL=30,
)
```

## 校验

配置在 `init_app()` 时校验。类型错误或缺少必填项（启用时的 `XXL_JOB_EXECUTOR_APP_NAME` 以及至少一个 `XXL_JOB_ADMIN_ADDRESSES` 条目）会抛出 `XXLJobConfigError`。错误配置绝不会被静默忽略。

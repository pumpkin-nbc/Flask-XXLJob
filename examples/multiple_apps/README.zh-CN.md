[English](README.md) | [简体中文](README.zh-CN.md)

# 多应用示例

演示一个共享的 `FlaskXXLJob` 实例服务两个 Flask 应用，每个应用通过
`set_run_callback(app, "名称", func)` 注册各自的命名请求处理函数。

## 运行

```bash
.venv\Scripts\python.exe examples\multiple_apps\app.py
```

每个应用拥有独立的运行时与注册表。Access Token 从 `XXL_JOB_ACCESS_TOKEN` 环境变量
读取；不提交任何真实 Token 或内网地址。

[English](README.md) | [简体中文](README.zh-CN.md)

# 注册状态示例

演示如何用 `get_status` 查询插件运行状态、用 `start_registry` / `stop_registry`
控制自动注册线程，以及 `xxljob status` CLI 命令。

## 运行

```bash
.venv\Scripts\python.exe examples\registry_status\app.py
```

状态只描述插件本身（是否启用、是否自动注册、是否已注册、最近一次注册结果），绝不
包含 Access Token 或任何业务状态。不提交任何真实 Token 或内网地址。

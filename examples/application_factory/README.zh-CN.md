[English](README.md) | [简体中文](README.zh-CN.md)

# Application Factory 示例

使用推荐的 Application Factory 模式，并配合模块级扩展实例的示例。
示例中的 Run Handler 名称为 `demoJobHandler`。

## 运行

```bash
.venv\Scripts\python.exe examples\application_factory\run.py
```

通过 CLI 注册执行器：

```bash
flask --app "examples.application_factory.app:create_app" xxljob register
```

Access Token 从 `XXL_JOB_ACCESS_TOKEN` 环境变量读取；仓库中不提交任何真实 Token 或内网地址。

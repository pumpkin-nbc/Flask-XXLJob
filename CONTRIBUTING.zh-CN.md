[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING.zh-CN.md)

# 贡献指南

感谢你有兴趣改进 Flask-XXLJob。

## 项目范围

Flask-XXLJob 是 Flask 与 XXL-JOB 2.4.1 之间的**协议适配插件**。它不得引入任务执行相关功能，例如线程池、进程池、Celery、Redis、SQLAlchemy、TaskStore 或 Callback Outbox。请将贡献控制在协议适配范围内。

## 环境

始终使用项目本地的 `.venv`。不要创建其他虚拟环境，也不要使用系统 Python。

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 检查

在提交 Pull Request 前运行完整检查：

```bash
.venv\Scripts\python.exe -m ruff check flask_xxljob
.venv\Scripts\python.exe -m mypy flask_xxljob
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py --dist-dir <clean-build-dir>
```

制品检查前请构建到新的空目录，不要复用 `dist/` 中的历史文件。安装后 Wheel 冒烟所需
独立临时虚拟环境是上述开发环境规则的发布验证例外。详见[发布](docs/publishing.zh-CN.md)。

## 文档

每个面向用户和开发者的文档都必须同时提供英文（`.md`）与简体中文（`.zh-CN.md`）版本。修改任一语言时，请在同一个 Pull Request 中同步更新另一语言，并保持代码示例一致。

## 协议准确性

任何协议改动都必须以官方 XXL-JOB 2.4.1 源码为准进行核对，包括字段的精确拼写（例如 `logDateTim` 与 `glueUpdatetime`）。

## 许可证

除非贡献者另有明确声明，提交并纳入 Flask-XXLJob 的贡献均按 [Apache License 2.0](LICENSE) 授权。

[English](development.md) | [简体中文](development.zh-CN.md)

# 开发

始终使用项目本地的 `.venv`。不要创建其他虚拟环境，也不要使用系统 Python。

## 环境准备

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 检查

```bash
.venv\Scripts\python.exe -m ruff check flask_xxljob
.venv\Scripts\python.exe -m mypy flask_xxljob
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\check_docs.py
```

## 目录结构

Python 包位于仓库根目录的 `flask_xxljob/`（不使用 `src/` 布局）。模块按职责拆分：`model/`、`response/`、`protocol/`、`client/`、`registry/`、`callback/`、`cli/` 与 `utils/`。

## 范围约束

Flask-XXLJob 是协议适配插件。不要加入任务执行、线程/进程池、Celery、Redis、SQLAlchemy、TaskStore 或 Callback Outbox。绝不使用 `eval` 或 `exec`，也绝不动态导入 `pkg/module/func`。

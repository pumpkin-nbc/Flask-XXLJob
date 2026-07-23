[English](development.md) | [简体中文](development.zh-CN.md)

# Development

Always use the project's local `.venv`. Do not create another virtual
environment or use the system Python.

## Setup

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Checks

```bash
.venv\Scripts\python.exe -m ruff check flask_xxljob
.venv\Scripts\python.exe -m mypy flask_xxljob
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\check_docs.py
```

## Layout

The package lives in `flask_xxljob/` at the repository root (no `src/` layout).
Modules are split by responsibility: `model/`, `response/`, `protocol/`,
`client/`, `registry/`, `callback/`, `cli/` and `utils/`.

## Scope rule

Flask-XXLJob is a protocol adapter. Do not add task execution, thread/process
pools, Celery, Redis, SQLAlchemy, task stores or callback outboxes. Never use
`eval` or `exec`, and never dynamically import `pkg/module/func`.

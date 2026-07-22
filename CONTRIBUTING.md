[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING.zh-CN.md)

# Contributing

Thanks for your interest in improving Flask-XXLJob.

## Scope

Flask-XXLJob is a **protocol adapter** between Flask and XXL-JOB 2.4.1. It must
not gain task-execution features such as thread pools, process pools, Celery,
Redis, SQLAlchemy, task stores or callback outboxes. Please keep contributions
within the protocol-adapter scope.

## Environment

Always use the project's local `.venv`. Do not create another virtual
environment or use the system Python.

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Checks

Run the full check set before opening a pull request:

```bash
.venv\Scripts\python.exe -m ruff check flask_xxljob
.venv\Scripts\python.exe -m mypy flask_xxljob
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py
```

## Documentation

Every user-facing and developer document must exist in both English (`.md`)
and Simplified Chinese (`.zh-CN.md`). When you change one language, update the
other in the same pull request and keep code examples identical.

## Protocol accuracy

Any protocol change must be verified against the official XXL-JOB 2.4.1 source,
including exact field spelling (for example `logDateTim` and `glueUpdatetime`).

## License

Unless you explicitly state otherwise, contributions submitted for inclusion in
Flask-XXLJob are licensed under the [Apache License 2.0](LICENSE).

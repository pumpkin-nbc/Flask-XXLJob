[English](publishing.md) | [简体中文](publishing.zh-CN.md)

# Publishing

All build and publish commands use the project's local `.venv`.

## Build

```bash
.venv\Scripts\python.exe -m build
```

This produces a wheel and a source distribution in `dist/`:

```text
dist/
  flask_xxljob-0.1.0-py3-none-any.whl
  flask_xxljob-0.1.0.tar.gz
```

## Check

```bash
.venv\Scripts\python.exe -m twine check dist/*
```

## Upload to TestPyPI

```bash
.venv\Scripts\python.exe -m twine upload --repository testpypi dist/*
```

Then install from TestPyPI to verify:

```bash
pip install --index-url https://test.pypi.org/simple/ Flask-XXLJob
```

## Upload to PyPI

```bash
.venv\Scripts\python.exe -m twine upload dist/*
```

## Before publishing

Run the documentation consistency check and ensure no secrets, internal
hostnames or tokens are included in the artifacts:

```bash
.venv\Scripts\python.exe scripts\check_docs.py
```

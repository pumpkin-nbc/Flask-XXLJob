[English](publishing.md) | [简体中文](publishing.zh-CN.md)

# 发布

所有构建与发布命令都使用项目本地的 `.venv`。

## 构建

```bash
.venv\Scripts\python.exe -m build
```

该命令会在 `dist/` 生成 wheel 与源码分发包：

```text
dist/
  flask_xxljob-0.2.0-py3-none-any.whl
  flask_xxljob-0.2.0.tar.gz
```

## 检查

```bash
.venv\Scripts\python.exe -m twine check dist/*
```

## 上传到 TestPyPI

```bash
.venv\Scripts\python.exe -m twine upload --repository testpypi dist/*
```

随后从 TestPyPI 安装以验证：

```bash
pip install --index-url https://test.pypi.org/simple/ Flask-XXLJob
```

## 上传到 PyPI

```bash
.venv\Scripts\python.exe -m twine upload dist/*
```

## 发布前

运行文档一致性检查，并确认产物中不包含任何密钥、内部域名或 Token：

```bash
.venv\Scripts\python.exe scripts\check_docs.py
```

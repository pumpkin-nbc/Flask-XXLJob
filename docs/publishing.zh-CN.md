[English](publishing.md) | [简体中文](publishing.zh-CN.md)

# 发布

发布使用 GitHub Actions Trusted Publishing，仓库中不保存长期 PyPI API Token。
本地命令只负责构建和检查制品；上传由 `.github/workflows/release.yml` 执行。

## 构建

```bash
.venv\Scripts\python.exe -m build
```

该命令会在 `dist/` 生成 wheel 与源码分发包：

```text
dist/
  flask_xxljob-0.3.1-py3-none-any.whl
  flask_xxljob-0.3.1.tar.gz
```

## 检查

```bash
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py
.venv\Scripts\python.exe -m twine check dist\flask_xxljob-0.3.1-py3-none-any.whl dist\flask_xxljob-0.3.1.tar.gz
```

## 配置 Trusted Publishing

在 PyPI 与 TestPyPI 创建 Pending Trusted Publisher：

- Project：`flask-xxljob`
- Owner：`pumpkin-nbc`
- Repository：`Flask-XXLJob`
- Workflow：`release.yml`
- PyPI Environment：`pypi`
- TestPyPI Environment：`testpypi`

同时创建同名 GitHub Environments，并要求 `pypi` Environment 必须人工审批。

## 发布到 TestPyPI

在 GitHub Actions 中手动运行 `Release` 工作流。`workflow_dispatch` 会只构建一次，
检查制品后发布到 `testpypi` Environment。

请在干净环境中验证指定测试版本。依赖可能不存在于 TestPyPI，因此先从 PyPI 安装依赖，
再使用 `--no-deps` 从 TestPyPI 安装本包：

```bash
python -m pip install --index-url https://pypi.org/simple Flask requests
python -m pip install --index-url https://test.pypi.org/simple --no-deps flask-xxljob==0.3.1
python -c "import flask_xxljob; assert flask_xxljob.__version__ == '0.3.1'"
flask-xxljob --version
```

## 发布到 PyPI

等待 `develop` 与 `master` 的完整 CI 矩阵通过后，从属于 `master` 的提交创建发布 Tag：

```bash
git tag -a v0.3.1 -m "Release 0.3.1"
git push origin v0.3.1
```

Tag 会触发同一个 `Release` 工作流。工作流会校验 `v0.3.1`、
`flask_xxljob/_version.py` 和两份 Changelog 一致，并确认 Tag 提交属于 `master`；
随后由 `pypi` Environment 的人工审批控制最终 Trusted Publishing 步骤。

## 发布前

运行上述全部检查，确认 wheel 与源码分发包包含 `LICENSE` 和 `NOTICE`、声明
`Apache-2.0`、使用真实项目链接，并且不包含任何密钥、内部域名或 Token：

```bash
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py
.venv\Scripts\python.exe -m twine check dist\flask_xxljob-0.3.1-py3-none-any.whl dist\flask_xxljob-0.3.1.tar.gz
```

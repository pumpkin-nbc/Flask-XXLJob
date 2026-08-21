[English](publishing.md) | [简体中文](publishing.zh-CN.md)

# 发布

发布使用 GitHub Actions Trusted Publishing，仓库中不保存长期 PyPI API Token。
本地命令只负责构建和检查制品；上传由 `.github/workflows/release.yml` 执行。

## 构建

使用新的空目录构建，避免历史 `dist/` 文件被误认为本轮制品。PowerShell 示例：

```powershell
$buildDir = Join-Path $env:TEMP "flask-xxljob-0.4.0-dist"
Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $buildDir | Out-Null
.venv\Scripts\python.exe -m build --outdir $buildDir
```

干净目录中必须恰好包含：

```text
flask_xxljob-0.4.0-py3-none-any.whl
flask_xxljob-0.4.0.tar.gz
```

## 检查

```powershell
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py --dist-dir $buildDir
.venv\Scripts\python.exe -m twine check `
  (Join-Path $buildDir "flask_xxljob-0.4.0-py3-none-any.whl") `
  (Join-Path $buildDir "flask_xxljob-0.4.0.tar.gz")
```

项目专用 Validator 会检查 wheel RECORD 的文件/hash/size 双向关系、拒绝 Wheel 签名
文件、读取 sdist 标准顶层 `PKG-INFO`、比较两种制品的名称和版本、检查源码、类型与
法律文件，并拒绝缓存和开发目录。它只验证本轮 Flask-XXLJob 制品，不是
通用 Wheel/sdist 验证器。

## 隔离安装后冒烟

在源码 checkout 外创建独立虚拟环境与工作目录，只安装新 wheel 及其依赖，执行
`pip check`，把 `scripts/smoke_installed_wheel.py` 复制到临时工作目录，清除
`PYTHONPATH` 后从那里运行。冒烟会确认 `flask_xxljob.__file__` 来自该环境的
`site-packages`，且现有包版本与制品元数据均为0.4.0；随后覆盖五个执行器端点、
Callback Client、两套CLI以及成功/失败的终止型Remove生命周期。

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
python -m pip install --index-url https://test.pypi.org/simple --no-deps flask-xxljob==0.4.0
python -c "import flask_xxljob; assert flask_xxljob.__version__ == '0.4.0'"
flask-xxljob --version
```

## 发布到 PyPI

等待 `develop` 与 `master` 的完整 CI 矩阵通过后，从属于 `master` 的提交创建发布 Tag：

```bash
git tag -a v0.4.0 -m "Release 0.4.0"
git push origin v0.4.0
```

Tag 会触发同一个 `Release` 工作流。工作流会校验 `v0.4.0`、
`flask_xxljob/_version.py` 和两份 Changelog 一致，并确认 Tag 提交属于 `master`；
随后由 `pypi` Environment 的人工审批控制最终 Trusted Publishing 步骤。

## 发布前

运行上述全部检查，确认 wheel 与源码分发包包含 `LICENSE` 和 `NOTICE`、声明
`Apache-2.0`、使用真实项目链接，并且不包含任何密钥、内部域名或 Token：

使用上面的干净 `$buildDir` 命令；不要检查混有历史文件的 `dist/`，也不要直接在源码
checkout 中运行安装后冒烟。

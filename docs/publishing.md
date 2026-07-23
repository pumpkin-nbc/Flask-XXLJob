[English](publishing.md) | [简体中文](publishing.zh-CN.md)

# Publishing

Releases use GitHub Actions Trusted Publishing. No long-lived PyPI API token is
stored in the repository. Local commands only build and inspect distributions;
uploading is performed by `.github/workflows/release.yml`.

## Build

```bash
.venv\Scripts\python.exe -m build
```

This produces a wheel and a source distribution in `dist/`:

```text
dist/
  flask_xxljob-0.3.1-py3-none-any.whl
  flask_xxljob-0.3.1.tar.gz
```

## Check

```bash
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py
.venv\Scripts\python.exe -m twine check dist\flask_xxljob-0.3.1-py3-none-any.whl dist\flask_xxljob-0.3.1.tar.gz
```

## Configure Trusted Publishing

Create Pending Trusted Publishers on PyPI and TestPyPI with:

- Project: `flask-xxljob`
- Owner: `pumpkin-nbc`
- Repository: `Flask-XXLJob`
- Workflow: `release.yml`
- PyPI environment: `pypi`
- TestPyPI environment: `testpypi`

Create matching GitHub Environments. The `pypi` environment must require manual
approval.

## Publish to TestPyPI

Run the `Release` workflow manually from GitHub Actions. A
`workflow_dispatch` run builds once, validates the artifacts, and publishes
them to the `testpypi` environment.

Verify the exact test version in a clean environment. Install dependencies from
PyPI first because they may not exist on TestPyPI, then install the package
from TestPyPI without dependency resolution:

```bash
python -m pip install --index-url https://pypi.org/simple Flask requests
python -m pip install --index-url https://test.pypi.org/simple --no-deps flask-xxljob==0.3.1
python -c "import flask_xxljob; assert flask_xxljob.__version__ == '0.3.1'"
flask-xxljob --version
```

## Publish to PyPI

After the complete CI matrix has passed on `develop` and `master`, create the
release tag from a commit contained in `master`:

```bash
git tag -a v0.3.1 -m "Release 0.3.1"
git push origin v0.3.1
```

The tag starts the same `Release` workflow. It verifies that `v0.3.1`,
`flask_xxljob/_version.py`, and both Changelogs agree and that the tagged commit
belongs to `master`. The `pypi` environment approval then gates the final
Trusted Publishing step.

## Before publishing

Run all checks above and confirm that the wheel and source distribution contain
`LICENSE` and `NOTICE`, declare `Apache-2.0`, use the real project URLs, and do
not include secrets, internal hostnames or tokens.

```bash
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py
.venv\Scripts\python.exe -m twine check dist\flask_xxljob-0.3.1-py3-none-any.whl dist\flask_xxljob-0.3.1.tar.gz
```

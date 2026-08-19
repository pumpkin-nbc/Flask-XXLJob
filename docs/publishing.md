[English](publishing.md) | [简体中文](publishing.zh-CN.md)

# Publishing

Releases use GitHub Actions Trusted Publishing. No long-lived PyPI API token is
stored in the repository. Local commands only build and inspect distributions;
uploading is performed by `.github/workflows/release.yml`.

## Build

Build into a new, empty directory so historical files under `dist/` cannot be
mistaken for this release. PowerShell example:

```powershell
$buildDir = Join-Path $env:TEMP "flask-xxljob-0.4.0-dist"
Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $buildDir | Out-Null
.venv\Scripts\python.exe -m build --outdir $buildDir
```

The clean directory must contain exactly:

```text
flask_xxljob-0.4.0-py3-none-any.whl
flask_xxljob-0.4.0.tar.gz
```

## Check

```powershell
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\check_package.py --dist-dir $buildDir
.venv\Scripts\python.exe -m twine check `
  (Join-Path $buildDir "flask_xxljob-0.4.0-py3-none-any.whl") `
  (Join-Path $buildDir "flask_xxljob-0.4.0.tar.gz")
```

The project-specific validator checks wheel RECORD file/hash/size mappings,
rejects Wheel signature files, verifies the standard top-level sdist
`PKG-INFO`, compares wheel/sdist names and versions, checks required source,
typing and legal files, caches and development directories.
It validates only freshly built Flask-XXLJob artifacts; it is not a general
Wheel or sdist validator.

## Isolated installed-wheel smoke

Create a separate virtual environment and working directory outside the source
checkout. Install only the new wheel and its dependencies, run `pip check`, copy
`scripts/smoke_installed_wheel.py` into the temporary working directory, clear
`PYTHONPATH`, and execute it from there. The smoke test fails unless
`flask_xxljob.__file__` comes from that environment's `site-packages` and all
existing package/metadata version sources report 0.4.0. It exercises all five
executor endpoints, Callback Client, and both CLI implementations, including
successful and failed terminal Remove lifecycles.

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
python -m pip install --index-url https://test.pypi.org/simple --no-deps flask-xxljob==0.4.0
python -c "import flask_xxljob; assert flask_xxljob.__version__ == '0.4.0'"
flask-xxljob --version
```

## Publish to PyPI

After the complete CI matrix has passed on `develop` and `master`, create the
release tag from a commit contained in `master`:

```bash
git tag -a v0.4.0 -m "Release 0.4.0"
git push origin v0.4.0
```

The tag starts the same `Release` workflow. It verifies that `v0.4.0`,
`flask_xxljob/_version.py`, and both Changelogs agree and that the tagged commit
belongs to `master`. The `pypi` environment approval then gates the final
Trusted Publishing step.

## Before publishing

Run all checks above and confirm that the wheel and source distribution contain
`LICENSE` and `NOTICE`, declare `Apache-2.0`, use the real project URLs, and do
not include secrets, internal hostnames or tokens.

Use the clean `$buildDir` commands above; never validate a mixed historical
`dist/` directory or run the installed-wheel smoke from the source checkout.

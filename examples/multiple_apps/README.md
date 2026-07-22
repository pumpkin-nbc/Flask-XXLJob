[English](README.md) | [简体中文](README.zh-CN.md)

# Multiple applications example

Shows a single shared `FlaskXXLJob` instance serving two Flask applications,
each with its own request handler registered via `set_run_callback(app, ...)`.

## Run

```bash
.venv\Scripts\python.exe examples\multiple_apps\app.py
```

Each application owns an isolated runtime and registry. The access token is read
from the `XXL_JOB_ACCESS_TOKEN` environment variable; no real token or internal
address is committed.

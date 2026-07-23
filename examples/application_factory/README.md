[English](README.md) | [简体中文](README.zh-CN.md)

# Application Factory example

An example using the recommended Application Factory pattern with a
module-level extension instance.
Its sample Run callback is named `demoJobHandler`.

## Run

```bash
.venv\Scripts\python.exe examples\application_factory\run.py
```

Register the executor from the CLI:

```bash
flask --app "examples.application_factory.app:create_app" xxljob register
```

The access token is read from the `XXL_JOB_ACCESS_TOKEN` environment variable;
no real token or internal address is committed.

[English](README.md) | [简体中文](README.zh-CN.md)

# Registry status example

Shows how to query the plugin runtime status with `get_status` and control the
Registry lifecycle with `start_registry` / `stop_registry`, plus the
`xxljob status` CLI command.
Its sample Run callback is named `registryStatusJobHandler`.

## Run

```bash
.venv\Scripts\python.exe examples\registry_status\app.py
```

The status describes only the plugin (enabled, auto-register, registered, last
registration result) and never contains the access token or any business state.
No real token or internal address is committed.

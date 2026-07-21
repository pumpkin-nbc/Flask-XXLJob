[English](deployment.md) | [简体中文](deployment.zh-CN.md)

# Deployment

## Executor address

Set `XXL_JOB_EXECUTOR_ADDRESS` to a URL the XXL-JOB admin can reach. In
containerized or multi-host deployments this is usually the service address,
not `127.0.0.1`.

## Automatic registration

With `XXL_JOB_AUTO_REGISTER=True` the extension starts a daemon thread that
registers the executor and renews it every `XXL_JOB_REGISTRY_INTERVAL` seconds.
Registration failures are logged and never crash the application.

## Flask debug reloader

Under the Flask debug reloader the registration thread only starts in the
reloader child process (where `WERKZEUG_RUN_MAIN=true`), so it is not started
twice.

## Multiple processes

Each worker process that initializes the extension registers with the same
executor app name and address. Because the registry key is the address, running
several workers behind one address is fine; running workers with different
addresses registers multiple executor instances. Plan your process model
accordingly.

## Manual registration

You can disable auto-registration and register from the CLI instead:

```bash
flask --app "project:create_app" xxljob register
```

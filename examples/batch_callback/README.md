[English](README.md) | [简体中文](README.zh-CN.md)

# Batch callback example

Shows how to report several task results in a single official request using
`callback_many`.
Its sample Run callback is named `batchJobHandler`.

## Run

```bash
.venv\Scripts\python.exe examples\batch_callback\app.py
```

`callback_many` validates every item before sending, never auto-splits, and
rejects the whole batch if any item is invalid or the count exceeds
`XXL_JOB_CALLBACK_BATCH_MAX_SIZE`. The access token is read from the
`XXL_JOB_ACCESS_TOKEN` environment variable; no real token or internal address
is committed.

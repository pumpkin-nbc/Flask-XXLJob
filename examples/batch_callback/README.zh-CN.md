[English](README.md) | [简体中文](README.zh-CN.md)

# 批量回调示例

演示如何使用 `callback_many` 在一次官方请求中上报多个任务结果。
示例中的 Run Handler 名称为 `batchJobHandler`。

## 运行

```bash
.venv\Scripts\python.exe examples\batch_callback\app.py
```

`callback_many` 发送前会校验每一条，绝不自动拆分；任一条目非法或数量超过
`XXL_JOB_CALLBACK_BATCH_MAX_SIZE` 时整体拒绝。Access Token 从
`XXL_JOB_ACCESS_TOKEN` 环境变量读取；不提交任何真实 Token 或内网地址。

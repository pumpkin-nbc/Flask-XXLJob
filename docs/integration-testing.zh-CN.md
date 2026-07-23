[English](integration-testing.md) | [简体中文](integration-testing.zh-CN.md)

# 针对 XXL-JOB 2.4.1 的集成测试

单元测试与集成测试套件全部离线运行，HTTP 调用均被 mock。本文档描述**选择性开启**
的、针对真实 XXL-JOB 2.4.1 Admin 的集成测试，以及可重复的手动验证步骤。

这些测试**默认跳过**。它们需要网络与一个运行中的 Admin，因此 CI 不会自动执行。除非
确实运行过，否则不会声称任何结果为“通过”。

## 自动化的选择性测试

`tests/integration/test_official_admin.py` 仅在设置了 `XXLJOB_ADMIN_URL` 时运行。它会
注册执行器、查询状态并注销。

```bash
# Windows PowerShell
$env:XXLJOB_ADMIN_URL = "http://127.0.0.1:8080/xxl-job-admin"
$env:XXLJOB_ACCESS_TOKEN = "default_token"        # 可选
$env:XXLJOB_EXECUTOR_ADDRESS = "http://127.0.0.1:5001"  # 可选
.venv\Scripts\python.exe -m pytest tests/integration/test_official_admin.py -q
```

支持的环境变量：

- `XXLJOB_ADMIN_URL`（必填）：一个或多个 Admin 基础 URL，用逗号分隔。
- `XXLJOB_ACCESS_TOKEN`（可选）：Access Token；不填即无 Token 模式。
- `XXLJOB_EXECUTOR_ADDRESS`（可选）：Admin 回调所用的执行器地址。
- `XXLJOB_APP_NAME`（可选）：执行器应用名。

## 手动验证清单

针对真实 XXL-JOB 2.4.1 Admin 执行以下步骤以完整验证协议兼容性：

1. **注册 / 续约 / 注销**：以 `XXL_JOB_AUTO_REGISTER=True` 启动应用；确认执行器在
   Admin 中在线、持续续约，并在关闭后消失。
2. **五个接口**：触发 `/run`、`/idleBeat`、`/kill`、`/log`，并通过 Admin 确认
   `/beat` 健康。
3. **单条与批量回调**：使用 `callback` / `callback_success` / `callback_failure`
   及 `callback_many`；确认日志状态更新。
4. **Token 开启与关闭**：验证正确 Token 通过、错误 Token 被拒绝，且 Admin 未配置
   Token 时无 Token 模式可用。
5. **路由前缀**：设置 `XXL_JOB_ROUTE_PREFIX`，确认 Admin 可访问带前缀的接口。
6. **中文任务参数**：下发带中文 `executorParams` 的任务并确认解码正确。
7. **多个 Admin 地址**：配置两个 Admin，确认注册与回调的故障转移。

## 本地已验证矩阵（如实报告）

本环境在 2026-07-23 实际执行的仅有：

- 在干净项目 `.venv` 中使用 Python 3.12.13 与 Flask 3.1.3：371 项离线测试通过，
  2 项真实 Admin 测试按环境跳过，覆盖率 93.46%。
- `pip check`、Ruff、mypy、双语文档检查、wheel/sdist 检查与干净环境 wheel
  安装冒烟测试通过。

其余 Python/Flask 组合已在 CI（`.github/workflows/ci.yml`）中**配置**，
但**未在本地执行**。上述官方 XXL-JOB 2.4.1 集成测试因无可用的在线 Admin，本环境
**未执行**；两项跳过测试即为这些选择性检查。

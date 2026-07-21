[English](migration.md) | [简体中文](migration.zh-CN.md)

# 从 Java 中转迁移

以前，Python 任务需要经过 Java 执行器服务：

```text
XXL-JOB -> Java executor -> Java calls Python HTTP -> Python runs task
```

使用 Flask-XXLJob 后，Flask 项目直接作为执行器：

```text
XXL-JOB -> Flask (Flask-XXLJob) -> your on_run submits the task
```

## 步骤

1. 将 `Flask-XXLJob` 加入依赖，并在工厂函数中初始化扩展。
2. 将 `XXL_JOB_EXECUTOR_ADDRESS` 指向 Flask 服务，并沿用与 Java 执行器相同的 `XXL_JOB_ACCESS_TOKEN`。
3. 把原本在 Java 层提交任务的逻辑迁移到 `on_run` 处理函数中，调用你现有的任务服务。
4. 用任务工作端的 `callback_success` / `callback_failure` 调用替换 Java 侧的最终状态更新。
5. 使用相同的应用名称注册执行器，使现有任务绑定继续有效。

## 说明

任务路由、阻塞策略、超时与重试仍由 XXL-JOB Admin 管理。Flask-XXLJob 只负责协议中转；你的任务服务始终完全掌控执行过程。

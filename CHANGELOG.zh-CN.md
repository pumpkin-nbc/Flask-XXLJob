[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并遵循 [语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

## [0.1.0] - 2026-07-21

### 新增

- 实现官方 XXL-JOB 2.4.1 执行器协议的 Flask 扩展。
- 支持 Application Factory，应用间 Runtime 隔离并保存在 `app.extensions["xxljob"]`。
- 执行器接口：`/beat`、`/idleBeat`、`/run`、`/kill`、`/log`。
- 请求处理函数注册：`on_run`、`on_idle_beat`、`on_kill`、`on_log`。
- 使用官方 `XXL-JOB-ACCESS-TOKEN` 请求头的 Access Token 校验。
- 执行器注册、注销与自动续约。
- 任务结果回调客户端：`callback`、`callback_success`、`callback_failure`。
- 多个 Admin 地址与故障转移。
- Flask CLI 分组 `xxljob` 及独立的 `flask-xxljob` 控制台脚本。
- 中英文双语文档。

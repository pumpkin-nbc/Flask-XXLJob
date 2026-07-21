[English](SECURITY.md) | [简体中文](SECURITY.zh-CN.md)

# 安全策略

## 受支持的版本

安全修复面向最新发布的 `0.1.x` 系列。

## 漏洞报告

请通过私下方式向维护者报告疑似漏洞，而不要直接创建公开 Issue。请包含问题描述、复现步骤以及受影响的版本。

## Access Token 处理

Flask-XXLJob 使用官方 `XXL-JOB-ACCESS-TOKEN` 请求头。Access Token：

- 从不写入日志；
- 从不出现在异常信息中；
- 从不硬编码在示例项目中。

请通过 `XXL_JOB_ACCESS_TOKEN` 配置（建议来自环境变量），且切勿提交真实 Token、内部域名或内网 IP 地址。

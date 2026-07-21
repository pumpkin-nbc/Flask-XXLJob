[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-21

### Added

- Flask extension implementing the official XXL-JOB 2.4.1 executor protocol.
- Application Factory support with per-application runtime isolation stored in `app.extensions["xxljob"]`.
- Executor endpoints: `/beat`, `/idleBeat`, `/run`, `/kill`, `/log`.
- Request-callback registration: `on_run`, `on_idle_beat`, `on_kill`, `on_log`.
- Access token validation using the official `XXL-JOB-ACCESS-TOKEN` header.
- Executor registration, deregistration and automatic renewal.
- Task-result callback client: `callback`, `callback_success`, `callback_failure`.
- Multiple admin addresses with failover.
- Flask CLI group `xxljob` and standalone `flask-xxljob` console script.
- Bilingual (English and Simplified Chinese) documentation.

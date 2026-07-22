"""
针对真实 XXL-JOB 2.4.1 Admin 的选择性集成测试。

Opt-in integration tests against a real XXL-JOB 2.4.1 admin.

默认跳过。设置环境变量 ``XXLJOB_ADMIN_URL``（可选 ``XXLJOB_ACCESS_TOKEN``、
``XXLJOB_EXECUTOR_ADDRESS``、``XXLJOB_APP_NAME``）后才会运行，用于对接真实 Admin
验证注册/续约/注销与回调。这些测试需要网络与一个运行中的 Admin，CI 默认不执行。

Skipped by default. They run only when ``XXLJOB_ADMIN_URL`` is set (optionally
``XXLJOB_ACCESS_TOKEN``, ``XXLJOB_EXECUTOR_ADDRESS``, ``XXLJOB_APP_NAME``) and
exercise registration/renewal/removal and callbacks against a live admin. They
require network access and a running admin and are not executed in CI by
default.
"""

from __future__ import annotations

import os

import pytest

from flask_xxljob import FlaskXXLJob

ADMIN_URL = os.environ.get("XXLJOB_ADMIN_URL")

pytestmark = pytest.mark.skipif(
    not ADMIN_URL,
    reason="Set XXLJOB_ADMIN_URL to run official XXL-JOB 2.4.1 integration tests.",
)


def _make_extension():
    from flask import Flask

    app = Flask("official-integration")
    app.config.update(
        XXL_JOB_ADMIN_ADDRESSES=[a.strip() for a in ADMIN_URL.split(",") if a.strip()],
        XXL_JOB_ACCESS_TOKEN=os.environ.get("XXLJOB_ACCESS_TOKEN", ""),
        XXL_JOB_EXECUTOR_APP_NAME=os.environ.get("XXLJOB_APP_NAME", "flask-xxljob-it"),
        XXL_JOB_EXECUTOR_ADDRESS=os.environ.get(
            "XXLJOB_EXECUTOR_ADDRESS", "http://127.0.0.1:5001"
        ),
        XXL_JOB_AUTO_REGISTER=False,
    )
    ext = FlaskXXLJob(app)
    return app, ext


def test_register_and_remove_against_admin():
    app, ext = _make_extension()
    register = ext.register_executor(app)
    assert register.success is True, register.message
    remove = ext.remove_executor(app)
    assert remove.success is True, remove.message


def test_status_reflects_registration():
    app, ext = _make_extension()
    ext.register_executor(app)
    status = ext.get_status(app)
    assert status.registered is True
    assert status.last_registry_success is True

"""Shared pytest fixtures for Flask-XXLJob tests."""

from __future__ import annotations

from typing import Optional

import pytest
from flask import Flask

from flask_xxljob import FlaskXXLJob

BASE_CONFIG = {
    "XXL_JOB_ADMIN_ADDRESSES": ["http://admin-1:8080/xxl-job-admin"],
    "XXL_JOB_EXECUTOR_APP_NAME": "test-executor",
    "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
    "XXL_JOB_AUTO_REGISTER": False,
    "TESTING": True,
}


def make_app(extension: Optional[FlaskXXLJob] = None, name: str = "test_app", **overrides):
    """Build and initialize a Flask app with the given extension."""
    app = Flask(name)
    config = dict(BASE_CONFIG)
    config.update(overrides)
    app.config.update(config)
    ext = extension or FlaskXXLJob()
    ext.init_app(app)
    return app, ext


@pytest.fixture
def app_ext():
    app, ext = make_app()
    return app, ext


@pytest.fixture
def client(app_ext):
    app, _ = app_ext
    return app.test_client()

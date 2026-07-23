"""
Flask-XXLJob
============

一个实现官方 XXL-JOB 2.4.1 执行器协议的 Flask 扩展。它只负责 Flask 与 XXL-JOB
之间的协议适配，不负责实际任务执行。

A Flask extension that implements the official XXL-JOB 2.4.1 executor
protocol. It only adapts the protocol between Flask and XXL-JOB and does not
execute the actual tasks.

基本用法 / Basic usage::

    from flask import Flask
    from flask_xxljob import FlaskXXLJob, XXLJobResponse

    xxl_job = FlaskXXLJob()

    def create_app():
        app = Flask(__name__)
        app.config.update(
            XXL_JOB_ADMIN_ADDRESSES=["http://127.0.0.1:8080/xxl-job-admin"],
            XXL_JOB_EXECUTOR_APP_NAME="project-executor",
            XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
        )
        xxl_job.init_app(app)

        @xxl_job.on_run("demoJobHandler")
        def handle_run(request):
            return XXLJobResponse.success()

        return app
"""

from __future__ import annotations

import logging

from ._version import __version__
from .client import AdminCallResult, CallResult
from .exceptions import (
    FlaskXXLJobError,
    XXLJobAdminCallError,
    XXLJobAlreadyInitializedError,
    XXLJobCallbackError,
    XXLJobCallbackRegistrationError,
    XXLJobConfigError,
    XXLJobConfigurationError,
    XXLJobError,
    XXLJobInitializationError,
    XXLJobProtocolError,
    XXLJobRegistryError,
    XXLJobRequestError,
    XXLJobValidationError,
)
from .extension import FlaskXXLJob
from .model.callback import CallbackRequest
from .model.idle_beat import IdleBeatRequest
from .model.kill import KillRequest
from .model.log import LogRequest
from .model.registry import RegistryRequest
from .model.trigger import TriggerRequest
from .response.executor import XXLJobResponse
from .response.log import LogResponse
from .status import XXLJobStatus

logging.getLogger("flask_xxljob").addHandler(logging.NullHandler())

__all__ = [
    "__version__",
    "FlaskXXLJob",
    "TriggerRequest",
    "IdleBeatRequest",
    "KillRequest",
    "LogRequest",
    "LogResponse",
    "CallbackRequest",
    "RegistryRequest",
    "XXLJobResponse",
    "CallResult",
    "AdminCallResult",
    "XXLJobStatus",
    "FlaskXXLJobError",
    "XXLJobError",
    "XXLJobConfigError",
    "XXLJobConfigurationError",
    "XXLJobInitializationError",
    "XXLJobAlreadyInitializedError",
    "XXLJobCallbackRegistrationError",
    "XXLJobValidationError",
    "XXLJobRequestError",
    "XXLJobProtocolError",
    "XXLJobAdminCallError",
    "XXLJobCallbackError",
    "XXLJobRegistryError",
]

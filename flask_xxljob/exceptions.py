"""
Flask-XXLJob 异常类型。

Flask-XXLJob exception types.
"""

from __future__ import annotations


class XXLJobError(Exception):
    """
    所有 Flask-XXLJob 异常的基类。

    Base class for all Flask-XXLJob exceptions.
    """


class XXLJobConfigError(XXLJobError):
    """
    配置缺失或类型不正确时抛出。

    Raised when configuration is missing or has an incorrect type.
    """


class XXLJobAlreadyInitializedError(XXLJobError):
    """
    在同一个 Flask 应用上重复初始化扩展时抛出。

    Raised when the extension is initialized more than once for the same
    Flask application.
    """


class XXLJobCallbackError(XXLJobError):
    """
    调用 XXL-JOB Admin 回调接口失败时抛出。

    Raised when a callback request to the XXL-JOB admin fails.
    """

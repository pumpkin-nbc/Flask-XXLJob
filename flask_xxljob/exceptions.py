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


class XXLJobConfigurationError(XXLJobError):
    """
    配置缺失或类型不正确时抛出。

    Raised when configuration is missing or has an incorrect type.
    """


# 向后兼容别名：0.1.0 使用 ``XXLJobConfigError``。
# Backward-compatible alias: 0.1.0 used ``XXLJobConfigError``.
XXLJobConfigError = XXLJobConfigurationError


class XXLJobAlreadyInitializedError(XXLJobError):
    """
    在同一个 Flask 应用上重复初始化扩展时抛出。

    Raised when the extension is initialized more than once for the same
    Flask application.
    """


class XXLJobRequestError(XXLJobError):
    """
    调用参数无效时抛出（例如类型错误的整数参数）。

    Raised when call arguments are invalid (for example an integer argument
    with the wrong type).
    """


class XXLJobProtocolError(XXLJobError):
    """
    Admin 返回的响应无法按官方协议解析时抛出。

    Raised when an admin response cannot be parsed according to the official
    protocol.
    """


class XXLJobCallbackError(XXLJobError):
    """
    调用 XXL-JOB Admin 回调接口失败时抛出。

    Raised when a callback request to the XXL-JOB admin fails.
    """


class XXLJobRegistryError(XXLJobError):
    """
    执行器注册或注销失败时抛出。

    Raised when executor registration or deregistration fails.
    """

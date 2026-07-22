"""
Flask-XXLJob 异常类型。

Flask-XXLJob exception types.

所有异常都继承统一基类 :class:`FlaskXXLJobError`。为了兼容 0.1.x，旧的基类名
``XXLJobError`` 与部分旧异常名保留为别名或子类。异常信息中绝不包含 Access Token。

All exceptions inherit from the single base :class:`FlaskXXLJobError`. For
backward compatibility with 0.1.x, the old base name ``XXLJobError`` and some
old exception names are retained as aliases or subclasses. Exception messages
never contain the access token.
"""

from __future__ import annotations


class FlaskXXLJobError(Exception):
    """
    所有 Flask-XXLJob 异常的统一基类。

    The single base class for all Flask-XXLJob exceptions.
    """


# 向后兼容别名：0.1.x 使用 ``XXLJobError`` 作为基类。
# Backward-compatible alias: 0.1.x used ``XXLJobError`` as the base class.
XXLJobError = FlaskXXLJobError


class XXLJobConfigurationError(FlaskXXLJobError):
    """
    配置缺失或类型不正确时抛出。

    Raised when configuration is missing or has an incorrect type.
    """


# 向后兼容别名：0.1.0 使用 ``XXLJobConfigError``。
# Backward-compatible alias: 0.1.0 used ``XXLJobConfigError``.
XXLJobConfigError = XXLJobConfigurationError


class XXLJobInitializationError(FlaskXXLJobError):
    """
    扩展初始化相关错误的基类。

    Base class for extension-initialization errors.
    """


class XXLJobAlreadyInitializedError(XXLJobInitializationError):
    """
    在同一个 Flask 应用上重复初始化扩展时抛出。

    Raised when the extension is initialized more than once for the same
    Flask application.
    """


class XXLJobCallbackRegistrationError(FlaskXXLJobError):
    """
    请求处理函数注册失败时抛出（例如重复注册且未指定 ``replace=True``）。

    Raised when request-callback registration fails (for example a duplicate
    registration without ``replace=True``).
    """


class XXLJobValidationError(FlaskXXLJobError):
    """
    公共 API 参数无效时抛出（例如类型错误的整数参数）。

    Raised when public API arguments are invalid (for example an integer
    argument with the wrong type).
    """


# 向后兼容别名：0.1.1 使用 ``XXLJobRequestError``。
# Backward-compatible alias: 0.1.1 used ``XXLJobRequestError``.
XXLJobRequestError = XXLJobValidationError


class XXLJobProtocolError(FlaskXXLJobError):
    """
    Admin 返回的响应无法按官方协议解析时抛出。

    Raised when an admin response cannot be parsed according to the official
    protocol.
    """


class XXLJobAdminCallError(FlaskXXLJobError):
    """
    调用 XXL-JOB Admin 接口失败相关错误的基类。

    Base class for failures when calling XXL-JOB admin APIs.
    """


class XXLJobCallbackError(XXLJobAdminCallError):
    """
    调用 XXL-JOB Admin 回调接口失败时抛出。

    Raised when a callback request to the XXL-JOB admin fails.
    """


class XXLJobRegistryError(XXLJobAdminCallError):
    """
    执行器注册或注销失败时抛出。

    Raised when executor registration or deregistration fails.
    """

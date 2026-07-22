"""
Flask-XXLJob 配置读取与校验。

Flask-XXLJob configuration loading and validation.

配置只在 ``init_app()`` 阶段读取，模块导入阶段不访问 ``current_app``。

Configuration is only read during ``init_app()``; ``current_app`` is never
accessed at import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping

from .exceptions import XXLJobConfigError

# 默认配置值 / Default configuration values.
DEFAULTS: dict = {
    "XXL_JOB_ENABLED": True,
    "XXL_JOB_ADMIN_ADDRESSES": [],
    "XXL_JOB_ACCESS_TOKEN": "",
    "XXL_JOB_EXECUTOR_APP_NAME": "flask-xxljob-executor",
    "XXL_JOB_EXECUTOR_ADDRESS": "",
    "XXL_JOB_ROUTE_PREFIX": "",
    "XXL_JOB_AUTO_REGISTER": True,
    "XXL_JOB_REGISTRY_INTERVAL": 30,
    "XXL_JOB_HTTP_CONNECT_TIMEOUT": 3,
    "XXL_JOB_HTTP_READ_TIMEOUT": 5,
    "XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH": 10000,
    "XXL_JOB_MAX_REQUEST_SIZE": 1048576,
    "XXL_JOB_MAX_PARAM_LENGTH": 65536,
}


@dataclass
class XXLJobConfig:
    """
    经过校验的 Flask-XXLJob 运行时配置。

    Validated Flask-XXLJob runtime configuration.
    """

    enabled: bool = True
    admin_addresses: List[str] = field(default_factory=list)
    access_token: str = ""
    executor_app_name: str = "flask-xxljob-executor"
    executor_address: str = ""
    route_prefix: str = ""
    auto_register: bool = True
    registry_interval: int = 30
    http_connect_timeout: int = 3
    http_read_timeout: int = 5
    callback_message_max_length: int = 10000
    max_request_size: int = 1048576
    max_param_length: int = 65536

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "XXLJobConfig":
        """
        从 Flask ``app.config`` 构造并校验配置。

        Build and validate the configuration from a Flask ``app.config``.
        """
        merged = {key: config.get(key, default) for key, default in DEFAULTS.items()}

        enabled = _as_bool(merged, "XXL_JOB_ENABLED")
        auto_register = _as_bool(merged, "XXL_JOB_AUTO_REGISTER")

        access_token = _as_str(merged, "XXL_JOB_ACCESS_TOKEN")
        executor_app_name = _as_str(merged, "XXL_JOB_EXECUTOR_APP_NAME")
        executor_address = _normalize_address(
            _as_str(merged, "XXL_JOB_EXECUTOR_ADDRESS")
        )
        route_prefix = _as_str(merged, "XXL_JOB_ROUTE_PREFIX")

        admin_addresses = [
            _normalize_address(item)
            for item in _as_str_list(merged, "XXL_JOB_ADMIN_ADDRESSES")
        ]

        registry_interval = _as_positive_int(merged, "XXL_JOB_REGISTRY_INTERVAL")
        http_connect_timeout = _as_positive_int(merged, "XXL_JOB_HTTP_CONNECT_TIMEOUT")
        http_read_timeout = _as_positive_int(merged, "XXL_JOB_HTTP_READ_TIMEOUT")
        callback_message_max_length = _as_positive_int(
            merged, "XXL_JOB_CALLBACK_MESSAGE_MAX_LENGTH"
        )
        max_request_size = _as_positive_int(merged, "XXL_JOB_MAX_REQUEST_SIZE")
        max_param_length = _as_positive_int(merged, "XXL_JOB_MAX_PARAM_LENGTH")

        instance = cls(
            enabled=enabled,
            admin_addresses=admin_addresses,
            access_token=access_token,
            executor_app_name=executor_app_name,
            executor_address=executor_address,
            route_prefix=_normalize_prefix(route_prefix),
            auto_register=auto_register,
            registry_interval=registry_interval,
            http_connect_timeout=http_connect_timeout,
            http_read_timeout=http_read_timeout,
            callback_message_max_length=callback_message_max_length,
            max_request_size=max_request_size,
            max_param_length=max_param_length,
        )
        instance.validate()
        return instance

    def validate(self) -> None:
        """
        校验配置。

        - 扩展禁用时不做任何校验。
        - 仅当开启自动注册（``auto_register``）时，才要求 Admin 地址、执行器名称
          与执行器地址；这样仅提供协议接入而不注册的场景也能正常工作。
        - 提供了 Admin 地址或执行器地址时，必须为 ``http``/``https`` 方案。

        Validate the configuration.

        - No validation is performed when the extension is disabled.
        - The admin addresses, executor name and executor address are required
          only when auto-registration is enabled, so scenarios that provide the
          protocol endpoints without registering still work.
        - When provided, admin/executor addresses must use the ``http``/``https``
          scheme.
        """
        if not self.enabled:
            return

        if self.auto_register:
            if not self.executor_app_name:
                raise XXLJobConfigError(
                    "XXL_JOB_EXECUTOR_APP_NAME must not be empty when "
                    "XXL_JOB_AUTO_REGISTER is enabled."
                )
            if not self.admin_addresses:
                raise XXLJobConfigError(
                    "XXL_JOB_ADMIN_ADDRESSES must contain at least one admin "
                    "address when XXL_JOB_AUTO_REGISTER is enabled."
                )
            if not self.executor_address:
                raise XXLJobConfigError(
                    "XXL_JOB_EXECUTOR_ADDRESS must not be empty when "
                    "XXL_JOB_AUTO_REGISTER is enabled."
                )

        for address in self.admin_addresses:
            _validate_http_url("XXL_JOB_ADMIN_ADDRESSES", address)
        if self.executor_address:
            _validate_http_url("XXL_JOB_EXECUTOR_ADDRESS", self.executor_address)

    @property
    def timeout(self) -> tuple:
        """
        返回 requests 使用的 ``(connect, read)`` 超时元组。

        Return the ``(connect, read)`` timeout tuple used by requests.
        """
        return (self.http_connect_timeout, self.http_read_timeout)


def _as_bool(config: Mapping[str, Any], key: str) -> bool:
    value = config[key]
    if not isinstance(value, bool):
        raise XXLJobConfigError(
            f"{key} must be a boolean (True/False); got type "
            f"{type(value).__name__}."
        )
    return value


def _as_str(config: Mapping[str, Any], key: str) -> str:
    value = config[key]
    if value is None:
        return ""
    if not isinstance(value, str):
        raise XXLJobConfigError(
            f"{key} must be a string; got type {type(value).__name__}."
        )
    return value


def _as_str_list(config: Mapping[str, Any], key: str) -> List[str]:
    value = config[key]
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = []
        for item in value:
            if not isinstance(item, str):
                raise XXLJobConfigError(
                    f"{key} must be a list of non-empty strings; found a list "
                    f"item of type {type(item).__name__}."
                )
            items.append(item.strip())
    else:
        raise XXLJobConfigError(
            f"{key} must be a list of strings or a comma-separated string; got "
            f"type {type(value).__name__}."
        )
    return [item for item in items if item]


def _as_positive_int(config: Mapping[str, Any], key: str) -> int:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise XXLJobConfigError(
            f"{key} must be a positive integer; got type {type(value).__name__}."
        )
    if value <= 0:
        raise XXLJobConfigError(
            f"{key} must be a positive integer (> 0); got value {value}."
        )
    return value


def _normalize_address(value: str) -> str:
    # 去除首尾空格与多余尾部斜杠，保留上下文路径（如 /xxl-job-admin）。
    # Strip surrounding whitespace and redundant trailing slashes while
    # preserving any context path (e.g. /xxl-job-admin).
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped.rstrip("/")


def _validate_http_url(key: str, value: str) -> None:
    # 仅校验方案，不做严格 URL 解析，兼容带路径/端口的 Admin 地址。
    # Only validate the scheme, not a strict URL parse, to stay compatible with
    # admin addresses that carry a path or port.
    lowered = value.strip().lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise XXLJobConfigError(
            f"{key} must be an http/https URL (e.g. 'http://host:port/path'); "
            f"got '{value}'."
        )


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    normalized = "/" + prefix.strip("/")
    return normalized

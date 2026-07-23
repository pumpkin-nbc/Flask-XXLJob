"""
Flask-XXLJob 配置读取与校验。

Flask-XXLJob configuration loading and validation.

配置只在 ``init_app()`` 阶段读取，模块导入阶段不访问 ``current_app``。

Configuration is only read during ``init_app()``; ``current_app`` is never
accessed at import time.
"""

from __future__ import annotations

import codecs
import logging
from dataclasses import dataclass, field
from typing import Any, List, Mapping
from urllib.parse import urlsplit

from .exceptions import XXLJobConfigError
from .utils.url_utils import join_url

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
    "XXL_JOB_CALLBACK_BATCH_MAX_SIZE": 100,
    "XXL_JOB_ADMIN_RETRY_COUNT": 0,
    "XXL_JOB_ADMIN_RETRY_BACKOFF": 0.0,
    "XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR": True,
    "XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON": False,
    "XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR": False,
    "XXL_JOB_LOG_ENABLED": False,
    "XXL_JOB_LOG_FILE_ENABLED": True,
    "XXL_JOB_LOG_CONSOLE_ENABLED": True,
    "XXL_JOB_LOG_LEVEL": "INFO",
    "XXL_JOB_LOG_FORMAT": (
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    ),
    "XXL_JOB_LOG_DATE_FORMAT": "%Y-%m-%d %H:%M:%S",
    "XXL_JOB_LOG_PATH": "./logs",
    "XXL_JOB_LOG_FILENAME": "flask-xxljob.log",
    "XXL_JOB_LOG_ENCODING": "utf-8",
    "XXL_JOB_LOG_MAX_BYTES": 10 * 1024 * 1024,
    "XXL_JOB_LOG_BACKUP_COUNT": 5,
    "XXL_JOB_LOG_PROPAGATE": False,
}

LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


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
    callback_batch_max_size: int = 100
    admin_retry_count: int = 0
    admin_retry_backoff: float = 0.0
    admin_failover_on_http_error: bool = True
    admin_failover_on_invalid_json: bool = False
    admin_failover_on_business_error: bool = False
    log_enabled: bool = False
    log_file_enabled: bool = True
    log_console_enabled: bool = True
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    log_path: str = "./logs"
    log_filename: str = "flask-xxljob.log"
    log_encoding: str = "utf-8"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    log_propagate: bool = False

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "XXLJobConfig":
        """
        从 Flask ``app.config`` 构造并校验配置。

        Build and validate the configuration from a Flask ``app.config``.
        """
        merged = {key: config.get(key, default) for key, default in DEFAULTS.items()}

        enabled = _as_bool(merged, "XXL_JOB_ENABLED")
        auto_register = _as_bool(merged, "XXL_JOB_AUTO_REGISTER")

        raw_access_token = _as_str(merged, "XXL_JOB_ACCESS_TOKEN")
        access_token = raw_access_token if raw_access_token.strip() else ""
        executor_app_name = _as_str(merged, "XXL_JOB_EXECUTOR_APP_NAME")
        route_prefix = _normalize_prefix(_as_str(merged, "XXL_JOB_ROUTE_PREFIX"))
        executor_address = _apply_route_prefix(
            _normalize_address(_as_str(merged, "XXL_JOB_EXECUTOR_ADDRESS")),
            route_prefix,
        )

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
        callback_batch_max_size = _as_positive_int(
            merged, "XXL_JOB_CALLBACK_BATCH_MAX_SIZE"
        )
        admin_retry_count = _as_non_negative_int(merged, "XXL_JOB_ADMIN_RETRY_COUNT")
        admin_retry_backoff = _as_non_negative_float(
            merged, "XXL_JOB_ADMIN_RETRY_BACKOFF"
        )
        admin_failover_on_http_error = _as_bool(
            merged, "XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR"
        )
        admin_failover_on_invalid_json = _as_bool(
            merged, "XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON"
        )
        admin_failover_on_business_error = _as_bool(
            merged, "XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR"
        )
        log_enabled = _as_bool(merged, "XXL_JOB_LOG_ENABLED")
        log_file_enabled = _as_bool(merged, "XXL_JOB_LOG_FILE_ENABLED")
        log_console_enabled = _as_bool(merged, "XXL_JOB_LOG_CONSOLE_ENABLED")
        log_level = _as_choice(
            merged, "XXL_JOB_LOG_LEVEL", LOG_LEVELS, case="upper"
        )
        log_format = _as_non_empty_str(merged, "XXL_JOB_LOG_FORMAT")
        log_date_format = _as_str_strict(merged, "XXL_JOB_LOG_DATE_FORMAT")
        log_path = _as_non_empty_str(merged, "XXL_JOB_LOG_PATH")
        log_filename = _as_non_empty_str(merged, "XXL_JOB_LOG_FILENAME")
        log_encoding = _as_non_empty_str(merged, "XXL_JOB_LOG_ENCODING")
        log_max_bytes = _as_positive_int(merged, "XXL_JOB_LOG_MAX_BYTES")
        log_backup_count = _as_non_negative_int(
            merged, "XXL_JOB_LOG_BACKUP_COUNT"
        )
        log_propagate = _as_bool(merged, "XXL_JOB_LOG_PROPAGATE")
        _validate_log_encoding(log_encoding)
        _validate_log_format(log_format, log_date_format)

        instance = cls(
            enabled=enabled,
            admin_addresses=admin_addresses,
            access_token=access_token,
            executor_app_name=executor_app_name,
            executor_address=executor_address,
            route_prefix=route_prefix,
            auto_register=auto_register,
            registry_interval=registry_interval,
            http_connect_timeout=http_connect_timeout,
            http_read_timeout=http_read_timeout,
            callback_message_max_length=callback_message_max_length,
            max_request_size=max_request_size,
            max_param_length=max_param_length,
            callback_batch_max_size=callback_batch_max_size,
            admin_retry_count=admin_retry_count,
            admin_retry_backoff=admin_retry_backoff,
            admin_failover_on_http_error=admin_failover_on_http_error,
            admin_failover_on_invalid_json=admin_failover_on_invalid_json,
            admin_failover_on_business_error=admin_failover_on_business_error,
            log_enabled=log_enabled,
            log_file_enabled=log_file_enabled,
            log_console_enabled=log_console_enabled,
            log_level=log_level,
            log_format=log_format,
            log_date_format=log_date_format,
            log_path=log_path,
            log_filename=log_filename,
            log_encoding=log_encoding,
            log_max_bytes=log_max_bytes,
            log_backup_count=log_backup_count,
            log_propagate=log_propagate,
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
          scheme. ``XXL_JOB_ROUTE_PREFIX`` is appended to the executor address
          automatically when the configuration is loaded.
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


def _as_non_empty_str(config: Mapping[str, Any], key: str) -> str:
    value = _as_str(config, key)
    if not value:
        raise XXLJobConfigError(f"{key} must be a non-empty string.")
    return value


def _as_str_strict(config: Mapping[str, Any], key: str) -> str:
    value = config[key]
    if not isinstance(value, str):
        raise XXLJobConfigError(
            f"{key} must be a string; got type {type(value).__name__}."
        )
    return value


def _as_choice(
    config: Mapping[str, Any],
    key: str,
    allowed: frozenset,
    *,
    case: str,
) -> str:
    value = _as_str(config, key)
    normalized = value.upper() if case == "upper" else value.lower()
    if normalized not in allowed:
        expected = " or ".join(repr(item) for item in sorted(allowed))
        raise XXLJobConfigError(
            f"Invalid {key} value {value!r}; expected {expected}."
        )
    return normalized


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


def _as_non_negative_int(config: Mapping[str, Any], key: str) -> int:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise XXLJobConfigError(
            f"{key} must be a non-negative integer; got type "
            f"{type(value).__name__}."
        )
    if value < 0:
        raise XXLJobConfigError(
            f"{key} must be a non-negative integer (>= 0); got value {value}."
        )
    return value


def _as_non_negative_float(config: Mapping[str, Any], key: str) -> float:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise XXLJobConfigError(
            f"{key} must be a non-negative number; got type "
            f"{type(value).__name__}."
        )
    if value < 0:
        raise XXLJobConfigError(
            f"{key} must be a non-negative number (>= 0); got value {value}."
        )
    return float(value)


def _normalize_address(value: str) -> str:
    # 去除首尾空格与多余尾部斜杠，保留上下文路径（如 /xxl-job-admin）。
    # Strip surrounding whitespace and redundant trailing slashes while
    # preserving any context path (e.g. /xxl-job-admin).
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped.rstrip("/")


def _validate_http_url(key: str, value: str) -> None:
    # Validate scheme, host and port while allowing an Admin context path.
    try:
        parsed = urlsplit(value)
        _validated_port = parsed.port  # Validates the port syntax and range.
    except ValueError as exc:
        raise XXLJobConfigError(
            f"{key} must be a valid http/https URL (e.g. 'http://host:port/path'); "
            f"got '{value}'."
        ) from exc
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise XXLJobConfigError(
            f"{key} must be a valid http/https URL (e.g. 'http://host:port/path'); "
            f"got '{value}'."
        )


def _normalize_prefix(prefix: str) -> str:
    stripped = prefix.strip()
    if not stripped:
        return ""
    normalized = stripped.strip("/")
    if not normalized:
        return ""
    return "/" + normalized


def _apply_route_prefix(address: str, route_prefix: str) -> str:
    """
    将 ``XXL_JOB_ROUTE_PREFIX`` 自动附加到 ``XXL_JOB_EXECUTOR_ADDRESS``。

    ``XXL_JOB_EXECUTOR_ADDRESS`` 只需填写服务基础地址（协议/主机/端口，可含
    反向代理上下文路径）；路由前缀会在加载配置时自动拼接，供 Admin 回调执行器
    接口。若地址路径已以该前缀结尾，则保持不变（兼容旧配置中已手写前缀的情况）。

    Append ``XXL_JOB_ROUTE_PREFIX`` onto ``XXL_JOB_EXECUTOR_ADDRESS``.

    ``XXL_JOB_EXECUTOR_ADDRESS`` should be the service base URL (scheme/host/port,
    optional reverse-proxy context path). The route prefix is appended at load
    time so Admin can reach the executor endpoints. If the address path already
    ends with the prefix, it is left unchanged (compatible with older configs
    that included the prefix manually).
    """
    if not address or not route_prefix:
        return address
    path = (urlsplit(address).path or "").rstrip("/")
    path_segments = [segment for segment in path.split("/") if segment]
    prefix_segments = [
        segment for segment in route_prefix.strip("/").split("/") if segment
    ]
    if (
        prefix_segments
        and len(path_segments) >= len(prefix_segments)
        and path_segments[-len(prefix_segments) :] == prefix_segments
    ):
        return address
    return join_url(address, route_prefix)


def _validate_log_encoding(encoding: str) -> None:
    try:
        codecs.lookup(encoding)
    except LookupError as exc:
        raise XXLJobConfigError(
            f"XXL_JOB_LOG_ENCODING must name a valid text encoding; got {encoding!r}."
        ) from exc


def _validate_log_format(log_format: str, date_format: str) -> None:
    try:
        formatter = logging.Formatter(
            fmt=log_format,
            datefmt=date_format or None,
            validate=True,
        )
        record = logging.LogRecord(
            name="flask_xxljob.validation",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="validation",
            args=(),
            exc_info=None,
        )
        formatter.format(record)
    except (KeyError, TypeError, ValueError) as exc:
        raise XXLJobConfigError(
            "XXL_JOB_LOG_FORMAT is not a valid standard logging format."
        ) from exc

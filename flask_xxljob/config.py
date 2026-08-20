"""
Flask-XXLJob 配置读取与校验。

Flask-XXLJob configuration loading and validation.

配置只在 ``init_app()`` 阶段读取，模块导入阶段不访问 ``current_app``。

Configuration is only read during ``init_app()``; ``current_app`` is never
accessed at import time.
"""

from __future__ import annotations

import codecs
import ipaddress
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
    "XXL_JOB_DEREGISTER_ON_EXIT": False,
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
    deregister_on_exit: bool = False
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
        _validate_removed_configs(config)
        merged = {key: config.get(key, default) for key, default in DEFAULTS.items()}

        enabled = _as_bool(merged, "XXL_JOB_ENABLED")
        auto_register = _as_bool(merged, "XXL_JOB_AUTO_REGISTER")
        deregister_on_exit = _as_bool(merged, "XXL_JOB_DEREGISTER_ON_EXIT")

        raw_access_token = _as_str(merged, "XXL_JOB_ACCESS_TOKEN")
        access_token = raw_access_token if raw_access_token.strip() else ""
        executor_app_name = _as_str(merged, "XXL_JOB_EXECUTOR_APP_NAME")
        raw_route_prefix = _as_str_strict(
            merged, "XXL_JOB_ROUTE_PREFIX"
        )
        raw_executor_address = _as_str_strict(
            merged, "XXL_JOB_EXECUTOR_ADDRESS"
        )
        raw_admin_addresses = _as_str_list(
            merged, "XXL_JOB_ADMIN_ADDRESSES"
        )

        if enabled:
            route_prefix = _normalize_prefix(raw_route_prefix)
            executor_address = _apply_route_prefix(
                _normalize_address(raw_executor_address),
                route_prefix,
            )
            admin_addresses = [
                _normalize_address(item) for item in raw_admin_addresses
            ]
        else:
            # disabled 是总开关：这些字符串仍要满足基础配置类型，但不会被解释为
            # URL/Flask path，也不会组合出一个实际不会使用的执行器地址。
            # disabled is the master switch: retain the typed strings without
            # interpreting them as URLs/Flask paths or composing an unused URL.
            route_prefix = raw_route_prefix
            executor_address = raw_executor_address
            admin_addresses = raw_admin_addresses

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
            deregister_on_exit=deregister_on_exit,
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
        校验初始化阶段已经提供的配置字段。

        Validate fields supplied during initialization.

        - Registry completeness is validated separately, immediately before a
          Registry lifecycle or one-shot Registry RPC starts. This allows an
          application to initialize protocol endpoints without Admin settings.
        - When provided, admin/executor addresses must use the ``http``/``https``
          scheme. ``XXL_JOB_ROUTE_PREFIX`` is always appended to the executor
          address when the configuration is loaded.
        """
        if not self.enabled:
            return

        for address in self.admin_addresses:
            _validate_http_url("XXL_JOB_ADMIN_ADDRESSES", address)
        if self.executor_address:
            _validate_http_url("XXL_JOB_EXECUTOR_ADDRESS", self.executor_address)

    def validate_registry(self) -> None:
        """Validate configuration required by an enabled Registry operation."""
        if not isinstance(self.executor_app_name, str) or not self.executor_app_name:
            raise XXLJobConfigError(
                "XXL_JOB_EXECUTOR_APP_NAME must not be empty for Registry operations."
            )
        if not isinstance(self.admin_addresses, list) or not self.admin_addresses:
            raise XXLJobConfigError(
                "XXL_JOB_ADMIN_ADDRESSES must contain at least one admin address "
                "for Registry operations."
            )
        if not isinstance(self.executor_address, str) or not self.executor_address:
            raise XXLJobConfigError(
                "XXL_JOB_EXECUTOR_ADDRESS must not be empty for Registry operations."
            )
        for address in self.admin_addresses:
            if not isinstance(address, str):
                raise XXLJobConfigError(
                    "XXL_JOB_ADMIN_ADDRESSES must contain only strings."
                )
            _validate_http_url("XXL_JOB_ADMIN_ADDRESSES", address)
        _validate_http_url("XXL_JOB_EXECUTOR_ADDRESS", self.executor_address)
        values = {
            "XXL_JOB_REGISTRY_INTERVAL": self.registry_interval,
            "XXL_JOB_HTTP_CONNECT_TIMEOUT": self.http_connect_timeout,
            "XXL_JOB_HTTP_READ_TIMEOUT": self.http_read_timeout,
            "XXL_JOB_ADMIN_RETRY_COUNT": self.admin_retry_count,
            "XXL_JOB_ADMIN_RETRY_BACKOFF": self.admin_retry_backoff,
            "XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR": (
                self.admin_failover_on_http_error
            ),
            "XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON": (
                self.admin_failover_on_invalid_json
            ),
            "XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR": (
                self.admin_failover_on_business_error
            ),
        }
        _as_positive_int(values, "XXL_JOB_REGISTRY_INTERVAL")
        _as_positive_int(values, "XXL_JOB_HTTP_CONNECT_TIMEOUT")
        _as_positive_int(values, "XXL_JOB_HTTP_READ_TIMEOUT")
        _as_non_negative_int(values, "XXL_JOB_ADMIN_RETRY_COUNT")
        _as_non_negative_float(values, "XXL_JOB_ADMIN_RETRY_BACKOFF")
        _as_bool(values, "XXL_JOB_ADMIN_FAILOVER_ON_HTTP_ERROR")
        _as_bool(values, "XXL_JOB_ADMIN_FAILOVER_ON_INVALID_JSON")
        _as_bool(values, "XXL_JOB_ADMIN_FAILOVER_ON_BUSINESS_ERROR")

    @property
    def timeout(self) -> tuple:
        """
        返回 requests 使用的 ``(connect, read)`` 超时元组。

        Return the ``(connect, read)`` timeout tuple used by requests.
        """
        return (self.http_connect_timeout, self.http_read_timeout)


def _validate_removed_configs(config: Mapping[str, Any]) -> None:
    key = "XXL_JOB_AUTO_REGISTER_ON_INIT"
    if key not in config:
        return
    value = config[key]
    if value is False:
        message = (
            "XXL_JOB_AUTO_REGISTER_ON_INIT 已删除。\n\n"
            "如需保持手动 Registry 启动，请设置：\n\n"
            "XXL_JOB_AUTO_REGISTER=False\n\n"
            "然后在需要的生命周期显式调用：\n\n"
            "start_registry()"
        )
    elif value is True:
        message = (
            "XXL_JOB_AUTO_REGISTER_ON_INIT 已删除。\n\n"
            "请删除该配置，并保留：\n\n"
            "XXL_JOB_AUTO_REGISTER=True"
        )
    else:
        message = (
            "XXL_JOB_AUTO_REGISTER_ON_INIT 已删除，请删除该配置并使用 "
            "XXL_JOB_AUTO_REGISTER 控制 Registry 自动启动。"
        )
    raise XXLJobConfigError(message)


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
        items = value.split(",")
    elif isinstance(value, (list, tuple)):
        items = []
        for item in value:
            if not isinstance(item, str):
                raise XXLJobConfigError(
                    f"{key} must be a list of non-empty strings; found a list "
                    f"item of type {type(item).__name__}."
                )
            items.append(item)
    else:
        raise XXLJobConfigError(
            f"{key} must be a list of strings or a comma-separated string; got "
            f"type {type(value).__name__}."
        )
    # Preserve each raw URL token so whitespace cannot disappear before the
    # explicit URL character validation below.
    return [item for item in items if item != ""]


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
    # 只规范尾斜杠；首尾空白必须留给原始 URL 校验明确拒绝，不能静默修复。
    # Normalize trailing slashes only. Surrounding whitespace must remain
    # visible to raw URL validation instead of being silently repaired.
    if not value:
        return ""
    return value.rstrip("/")


def _validate_http_url(key: str, value: str) -> None:
    # Python versions have differed in how urlsplit handles control characters,
    # so reject the raw input before parsing for stable security semantics.
    if any(
        ord(character) < 0x20
        or ord(character) == 0x7F
        or character.isspace()
        for character in value
    ):
        raise XXLJobConfigError(
            f"{key} must be a valid http/https URL without whitespace or "
            "control characters."
        )

    try:
        parsed = urlsplit(value)
        port = parsed.port  # Validates the port syntax and range.
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
    except ValueError as exc:
        raise XXLJobConfigError(
            f"{key} must be a valid http/https URL with a valid host and port."
        ) from exc

    invalid = bool(
        parsed.scheme.lower() not in ("http", "https")
        or not hostname
        or not _is_valid_hostname(hostname)
        or port == 0
        or username is not None
        or password is not None
        or parsed.query
        or parsed.fragment
        or "?" in value
        or "#" in value
    )
    if invalid:
        raise XXLJobConfigError(
            f"{key} must be a valid http/https URL with no userinfo, query, "
            "fragment, whitespace, or control characters."
        )


def _is_valid_hostname(hostname: str) -> bool:
    """Accept IP literals and DNS/IDNA hostnames, rejecting parser-only hosts."""
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass

    # A dotted numeric host must be a real IPv4 literal rather than a DNS-like
    # name that a downstream HTTP stack may interpret inconsistently.
    if all(character.isdigit() or character == "." for character in hostname):
        return False

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if ascii_hostname.endswith("."):
        ascii_hostname = ascii_hostname[:-1]
    if not ascii_hostname or len(ascii_hostname) > 253:
        return False

    for label in ascii_hostname.split("."):
        if not label or len(label) > 63:
            return False
        if not label[0].isalnum() or not label[-1].isalnum():
            return False
        if any(not (character.isalnum() or character == "-") for character in label):
            return False
    return True


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    if prefix == "/":
        return ""

    forbidden = {"?", "#", "%", "\\", "<", ">"}
    if any(
        character in forbidden
        or ord(character) < 0x20
        or ord(character) == 0x7F
        or character.isspace()
        for character in prefix
    ):
        raise XXLJobConfigError(
            "XXL_JOB_ROUTE_PREFIX must be a static Flask path without "
            "whitespace, control characters, query syntax, fragments, "
            "percent encoding, backslashes, or converters."
        )
    if "//" in prefix:
        raise XXLJobConfigError(
            "XXL_JOB_ROUTE_PREFIX must not contain consecutive slashes."
        )

    normalized = prefix
    if normalized.startswith("/"):
        normalized = normalized[1:]
    if normalized.endswith("/"):
        normalized = normalized[:-1]
    if not normalized or any(
        segment in {".", ".."} for segment in normalized.split("/")
    ):
        raise XXLJobConfigError(
            "XXL_JOB_ROUTE_PREFIX must be a static path without '.' or '..' "
            "segments."
        )
    return "/" + normalized


def _apply_route_prefix(address: str, route_prefix: str) -> str:
    """
    将 ``XXL_JOB_ROUTE_PREFIX`` 自动附加到 ``XXL_JOB_EXECUTOR_ADDRESS``。

    ``XXL_JOB_EXECUTOR_ADDRESS`` 只需填写服务基础地址（协议/主机/端口，可含
    反向代理上下文路径）；路由前缀会在加载配置时始终拼接，供 Admin 回调执行器
    接口。地址中若已手写同名路径段，仍会再附加一次前缀。

    Append ``XXL_JOB_ROUTE_PREFIX`` onto ``XXL_JOB_EXECUTOR_ADDRESS``.

    ``XXL_JOB_EXECUTOR_ADDRESS`` should be the service base URL (scheme/host/port,
    optional reverse-proxy context path). The route prefix is always appended at
    load time so Admin can reach the executor endpoints. If the address already
    contains the same path segment, the prefix is still appended again.
    """
    if not address or not route_prefix:
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

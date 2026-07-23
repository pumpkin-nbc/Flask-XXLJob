"""
协议模型字段类型转换辅助。

Protocol-model field coercion helpers.
"""

from __future__ import annotations

from typing import Any


class ModelParseError(ValueError):
    """
    官方字段无法转换为期望类型时抛出。

    Raised when an official field cannot be converted to the expected type.
    """


def coerce_str(value: Any, field: str, default: str = "") -> str:
    """
    将官方字符串字段校验为 ``str``。

    缺失值（``None``）返回默认值；包括空字符串和纯空白字符串在内的
    ``str`` 值保持原样。其他类型不进行隐式字符串转换，而是抛出
    :class:`ModelParseError`。

    Validate an official string field as ``str``.

    A missing value (``None``) returns the default. String values, including
    empty and whitespace-only strings, are preserved unchanged. Other types
    are never converted implicitly and raise :class:`ModelParseError`.
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value
    raise ModelParseError(
        f"field '{field}' must be a string, got {type(value).__name__}"
    )


def coerce_int(value: Any, field: str, default: int = 0) -> int:
    """
    将官方数字字段转换为 ``int``。

    - 缺失（``None``）返回默认值。
    - ``0`` 保持为 ``0``，不被当作空值。
    - 合法整数或数字字符串正常转换。
    - 布尔值和无法转换的值抛出 :class:`ModelParseError`。

    Convert an official numeric field to ``int``.

    - A missing value (``None``) returns the default.
    - ``0`` stays ``0`` and is never treated as empty.
    - Valid integers or numeric strings are converted.
    - Booleans and non-convertible values raise :class:`ModelParseError`.
    """
    if value is None:
        return default
    # 布尔是 int 的子类，但协议数字字段不接受布尔。
    # bool is a subclass of int, but protocol numeric fields reject booleans.
    if isinstance(value, bool):
        raise ModelParseError(f"field '{field}' must be an integer, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ModelParseError(f"field '{field}' must be an integer, got a fractional number")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(stripped)
        except ValueError as exc:
            raise ModelParseError(
                f"field '{field}' must be an integer, got a non-numeric string"
            ) from exc
    raise ModelParseError(f"field '{field}' must be an integer, got {type(value).__name__}")

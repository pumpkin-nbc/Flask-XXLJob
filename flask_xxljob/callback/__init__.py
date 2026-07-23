"""
Flask-XXLJob 请求处理函数注册表。

Flask-XXLJob request-callback registry.
"""

from __future__ import annotations

from .registry import CallbackRegistry

__all__ = ["CallbackRegistry"]

"""
Flask-XXLJob 协议请求模型。

Flask-XXLJob protocol request models.
"""

from __future__ import annotations

from .callback import CallbackRequest
from .idle_beat import IdleBeatRequest
from .kill import KillRequest
from .log import LogRequest
from .registry import REGISTRY_GROUP_EXECUTOR, RegistryRequest
from .trigger import TriggerRequest

__all__ = [
    "CallbackRequest",
    "IdleBeatRequest",
    "KillRequest",
    "LogRequest",
    "RegistryRequest",
    "REGISTRY_GROUP_EXECUTOR",
    "TriggerRequest",
]

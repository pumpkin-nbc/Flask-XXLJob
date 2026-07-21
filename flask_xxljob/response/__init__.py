"""
Flask-XXLJob 响应模型。

Flask-XXLJob response models.
"""

from __future__ import annotations

from .executor import FAIL_CODE, SUCCESS_CODE, XXLJobResponse
from .log import LogResponse

__all__ = [
    "XXLJobResponse",
    "LogResponse",
    "SUCCESS_CODE",
    "FAIL_CODE",
]

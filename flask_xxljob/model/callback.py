"""
XXL-JOB ``/api/callback`` 请求模型。

XXL-JOB ``/api/callback`` request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .coerce import coerce_int, coerce_str


@dataclass
class CallbackRequest:
    """
    官方 ``HandleCallbackParam`` 的类型化 Python 表示。

    注意：官方线路字段为 ``logDateTim``（缺少结尾字母 e），这是 XXL-JOB
    2.4.1 源码中的既有拼写，必须原样兼容。

    A typed Python representation of the official ``HandleCallbackParam``.

    Note: the official wire field is ``logDateTim`` (missing the trailing
    letter e). This spelling exists in the XXL-JOB 2.4.1 source and must be
    matched exactly.
    """

    log_id: int = 0
    log_date_time: int = 0
    handle_code: int = 200
    handle_msg: str = ""

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "CallbackRequest":
        """
        从官方 ``HandleCallbackParam`` JSON 字典构造对象。

        Build the object from an official ``HandleCallbackParam`` JSON mapping.
        """
        return cls(
            log_id=coerce_int(data.get("logId"), "logId"),
            log_date_time=coerce_int(data.get("logDateTim"), "logDateTim"),
            handle_code=coerce_int(data.get("handleCode"), "handleCode"),
            handle_msg=coerce_str(data.get("handleMsg"), "handleMsg"),
        )

    def to_wire(self) -> dict:
        """
        转换为官方 ``HandleCallbackParam`` JSON 字典。

        Convert to an official ``HandleCallbackParam`` JSON mapping.
        """
        return {
            "logId": self.log_id,
            "logDateTim": self.log_date_time,
            "handleCode": self.handle_code,
            "handleMsg": self.handle_msg,
        }

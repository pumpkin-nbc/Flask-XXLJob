"""
XXL-JOB ``/log`` 请求模型。

XXL-JOB ``/log`` request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .coerce import coerce_int


@dataclass
class LogRequest:
    """
    官方 ``LogParam`` 的类型化 Python 表示。

    注意：官方线路字段为 ``logDateTim``（缺少结尾字母 e），这是 XXL-JOB
    2.4.1 源码中的既有拼写，必须原样兼容。

    A typed Python representation of the official ``LogParam``.

    Note: the official wire field is ``logDateTim`` (missing the trailing
    letter e). This spelling exists in the XXL-JOB 2.4.1 source and must be
    matched exactly.
    """

    log_date_time: int = 0
    log_id: int = 0
    from_line_num: int = 0

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "LogRequest":
        """
        从官方 ``LogParam`` JSON 字典构造对象。

        Build the object from an official ``LogParam`` JSON mapping.
        """
        return cls(
            log_date_time=coerce_int(data.get("logDateTim"), "logDateTim"),
            log_id=coerce_int(data.get("logId"), "logId"),
            from_line_num=coerce_int(data.get("fromLineNum"), "fromLineNum"),
        )

    def to_wire(self) -> dict:
        """
        转换为官方 ``LogParam`` JSON 字典。

        Convert to an official ``LogParam`` JSON mapping.
        """
        return {
            "logDateTim": self.log_date_time,
            "logId": self.log_id,
            "fromLineNum": self.from_line_num,
        }

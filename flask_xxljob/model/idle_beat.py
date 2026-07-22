"""
XXL-JOB ``/idleBeat`` 请求模型。

XXL-JOB ``/idleBeat`` request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .coerce import coerce_int


@dataclass
class IdleBeatRequest:
    """
    官方 ``IdleBeatParam`` 的类型化 Python 表示。

    A typed Python representation of the official ``IdleBeatParam``.
    """

    job_id: int = 0

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "IdleBeatRequest":
        """
        从官方 ``IdleBeatParam`` JSON 字典构造对象。

        Build the object from an official ``IdleBeatParam`` JSON mapping.
        """
        return cls(job_id=coerce_int(data.get("jobId"), "jobId"))

    def to_wire(self) -> dict:
        """
        转换为官方 ``IdleBeatParam`` JSON 字典。

        Convert to an official ``IdleBeatParam`` JSON mapping.
        """
        return {"jobId": self.job_id}

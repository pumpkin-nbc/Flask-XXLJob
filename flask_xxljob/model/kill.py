"""
XXL-JOB ``/kill`` 请求模型。

XXL-JOB ``/kill`` request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .coerce import coerce_int


@dataclass
class KillRequest:
    """
    官方 ``KillParam`` 的类型化 Python 表示。

    A typed Python representation of the official ``KillParam``.
    """

    job_id: int = 0

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "KillRequest":
        """
        从官方 ``KillParam`` JSON 字典构造对象。

        Build the object from an official ``KillParam`` JSON mapping.
        """
        return cls(job_id=coerce_int(data.get("jobId"), "jobId"))

    def to_wire(self) -> dict:
        """
        转换为官方 ``KillParam`` JSON 字典。

        Convert to an official ``KillParam`` JSON mapping.
        """
        return {"jobId": self.job_id}

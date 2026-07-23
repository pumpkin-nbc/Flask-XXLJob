"""
XXL-JOB ``/run`` 触发请求模型。

XXL-JOB ``/run`` trigger request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..utils.json_utils import try_parse_json
from .coerce import coerce_int, coerce_str


@dataclass
class TriggerRequest:
    """
    官方 ``TriggerParam`` 的类型化 Python 表示。

    字段名称使用 snake_case，序列化时映射到官方 XXL-JOB 2.4.1 的
    camelCase 线路字段（包含官方拼写 ``glueUpdatetime``）。

    A typed Python representation of the official ``TriggerParam``.

    Attribute names use snake_case and are mapped to the official XXL-JOB
    2.4.1 camelCase wire fields (including the official spelling
    ``glueUpdatetime``) during serialization.
    """

    job_id: int = 0
    executor_handler: str = ""
    executor_params: str = ""
    executor_block_strategy: str = ""
    executor_timeout: int = 0
    log_id: int = 0
    log_date_time: int = 0
    glue_type: str = ""
    glue_source: str = ""
    glue_update_time: int = 0
    broadcast_index: int = 0
    broadcast_total: int = 0

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "TriggerRequest":
        """
        从官方 ``TriggerParam`` JSON 字典构造对象。

        Build the object from an official ``TriggerParam`` JSON mapping.
        """
        return cls(
            job_id=coerce_int(data.get("jobId"), "jobId"),
            executor_handler=coerce_str(
                data.get("executorHandler"), "executorHandler"
            ),
            executor_params=coerce_str(data.get("executorParams"), "executorParams"),
            executor_block_strategy=coerce_str(
                data.get("executorBlockStrategy"), "executorBlockStrategy"
            ),
            executor_timeout=coerce_int(data.get("executorTimeout"), "executorTimeout"),
            log_id=coerce_int(data.get("logId"), "logId"),
            log_date_time=coerce_int(data.get("logDateTime"), "logDateTime"),
            glue_type=coerce_str(data.get("glueType"), "glueType"),
            glue_source=coerce_str(data.get("glueSource"), "glueSource"),
            glue_update_time=coerce_int(data.get("glueUpdatetime"), "glueUpdatetime"),
            broadcast_index=coerce_int(data.get("broadcastIndex"), "broadcastIndex"),
            broadcast_total=coerce_int(data.get("broadcastTotal"), "broadcastTotal"),
        )

    def to_wire(self) -> dict:
        """
        转换为官方 ``TriggerParam`` JSON 字典。

        Convert to an official ``TriggerParam`` JSON mapping.
        """
        return {
            "jobId": self.job_id,
            "executorHandler": self.executor_handler,
            "executorParams": self.executor_params,
            "executorBlockStrategy": self.executor_block_strategy,
            "executorTimeout": self.executor_timeout,
            "logId": self.log_id,
            "logDateTime": self.log_date_time,
            "glueType": self.glue_type,
            "glueSource": self.glue_source,
            "glueUpdatetime": self.glue_update_time,
            "broadcastIndex": self.broadcast_index,
            "broadcastTotal": self.broadcast_total,
        }

    def parse_params(self) -> Any:
        """
        解析 ``executor_params`` 的辅助方法，不修改原始字符串。

        - 空字符串或纯空白返回 ``None``。
        - 合法 JSON 返回对应 Python 对象。
        - 非 JSON 返回原始字符串。

        Parse ``executor_params`` without mutating the original string.

        - A blank or whitespace-only value returns ``None``.
        - Valid JSON returns the corresponding Python object.
        - Otherwise the original string is returned unchanged.
        """
        return try_parse_json(self.executor_params)

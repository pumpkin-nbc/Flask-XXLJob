"""
XXL-JOB ``/log`` 响应模型。

XXL-JOB ``/log`` response model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LogResponse:
    """
    官方 ``LogResult`` 的类型化 Python 表示。

    分页字段与官方协议保持一致：``from_line_num``、``to_line_num``、
    ``log_content``、``is_end``。

    A typed Python representation of the official ``LogResult``.

    The pagination fields match the official protocol: ``from_line_num``,
    ``to_line_num``, ``log_content`` and ``is_end``.
    """

    from_line_num: int = 0
    to_line_num: int = 0
    log_content: str = ""
    is_end: bool = False

    def to_wire(self) -> dict:
        """
        转换为官方 ``LogResult`` JSON 字典。

        Convert to an official ``LogResult`` JSON mapping.
        """
        return {
            "fromLineNum": self.from_line_num,
            "toLineNum": self.to_line_num,
            "logContent": self.log_content,
            "isEnd": self.is_end,
        }

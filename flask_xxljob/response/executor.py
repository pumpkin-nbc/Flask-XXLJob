"""
XXL-JOB 标准执行器响应模型。

XXL-JOB standard executor response model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# 官方状态码 / Official status codes.
SUCCESS_CODE = 200
FAIL_CODE = 500


@dataclass
class XXLJobResponse:
    """
    官方 ``ReturnT`` 的类型化 Python 表示。

    正常情况下 HTTP 状态码保持 200，业务结果通过 ``code`` 表示：成功为
    ``200``，失败为 ``500``。

    A typed Python representation of the official ``ReturnT``.

    The HTTP status code is normally kept at 200; the business result is
    conveyed through ``code`` (``200`` for success, ``500`` for failure).
    """

    code: int = SUCCESS_CODE
    msg: Optional[str] = None
    content: Any = None

    @classmethod
    def success(cls, msg: Optional[str] = None, content: Any = None) -> "XXLJobResponse":
        """
        构造成功响应。

        ``msg`` 可选，写入官方 ``ReturnT.msg``，默认 ``None``；``content`` 为
        第二个参数。

        Build a success response.

        ``msg`` is optional and maps to the official ``ReturnT.msg``; defaults
        to ``None``. ``content`` is the second argument.
        """
        return cls(code=SUCCESS_CODE, msg=msg, content=content)

    @classmethod
    def failure(cls, msg: str, content: Any = None) -> "XXLJobResponse":
        """
        构造失败响应。

        Build a failure response.
        """
        return cls(code=FAIL_CODE, msg=msg, content=content)

    @property
    def is_success(self) -> bool:
        """
        是否为成功响应。

        Whether this is a success response.
        """
        return self.code == SUCCESS_CODE

    def to_dict(self) -> dict:
        """
        转换为官方响应 JSON 字典。

        Convert to the official response JSON mapping.
        """
        return {"code": self.code, "msg": self.msg, "content": self.content}

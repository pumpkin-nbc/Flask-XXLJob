"""
XXL-JOB 任务结果回调客户端。

XXL-JOB task-result callback client.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..config import XXLJobConfig
from ..exceptions import XXLJobValidationError
from ..model.callback import CallbackRequest
from ..model.coerce import ModelParseError, coerce_str
from . import CallResult, post_to_admins
from .policy import AdminCallPolicy

# 官方 Admin 回调接口路径 / Official admin callback API path.
CALLBACK_PATH = "/api/callback"

# 可接受的批量回调条目类型 / Accepted batch callback item types.
CallbackLike = Union[CallbackRequest, dict]


class CallbackClient:
    """
    向官方 ``/api/callback`` 发送任务最终执行结果。

    客户端只负责构造并发送回调请求，不判断任务是否完成、不监控任务、不持久化、
    不后台无限重试、不创建后台线程。

    Sends the final task execution result to the official ``/api/callback``.

    The client only builds and sends callback requests. It does not decide
    whether a task is complete, monitor tasks, persist callbacks, retry
    indefinitely in the background, or create background threads.
    """

    def __init__(self, config: XXLJobConfig) -> None:
        self._config = config

    def callback(
        self,
        log_id: int,
        log_date_time: int,
        handle_code: int,
        handle_msg: Optional[str] = None,
    ) -> CallResult:
        """
        发送一次任务结果回调。

        官方 ``/api/callback`` 接收 ``HandleCallbackParam`` 数组，因此这里以
        单元素数组发送。``handle_msg`` 会被截断到配置的最大长度。

        Send a single task-result callback.

        The official ``/api/callback`` accepts an array of
        ``HandleCallbackParam``, so a single-element array is sent here.
        ``handle_msg`` is truncated to the configured maximum length.
        """
        request = CallbackRequest(
            log_id=log_id,
            log_date_time=log_date_time,
            handle_code=handle_code,
            handle_msg="" if handle_msg is None else handle_msg,
        )
        return self.callback_many([request])

    def callback_many(self, requests: Sequence[CallbackLike]) -> CallResult:
        """
        在一次官方请求中批量发送多条任务结果回调。

        - 发送前完整校验每一条：必须是 :class:`CallbackRequest` 或可转换的字典；
          ``log_id``/``log_date_time``/``handle_code`` 必须为整数（拒绝布尔值）；
          每条 ``handle_msg`` 按配置截断（Unicode 安全）。
        - 条目数不得超过 ``XXL_JOB_CALLBACK_BATCH_MAX_SIZE``；超出时抛出异常，绝不
          自动拆分或只发送部分。
        - 任一条目非法即整体拒绝（全有或全无），不会发送部分数据。

        Send multiple task-result callbacks in a single official request.

        - Every item is fully validated before sending: it must be a
          :class:`CallbackRequest` or a coercible mapping; ``log_id``,
          ``log_date_time`` and ``handle_code`` must be integers (booleans are
          rejected); each ``handle_msg`` is truncated per configuration
          (Unicode-safe).
        - The item count must not exceed ``XXL_JOB_CALLBACK_BATCH_MAX_SIZE``;
          exceeding it raises, and the batch is never auto-split or partially
          sent.
        - If any item is invalid the whole batch is rejected (all-or-nothing);
          no partial data is sent.
        """
        items = list(requests)
        if not items:
            raise XXLJobValidationError(
                "callback_many requires at least one callback request"
            )

        max_size = self._config.callback_batch_max_size
        if len(items) > max_size:
            raise XXLJobValidationError(
                f"callback batch size {len(items)} exceeds the configured "
                f"maximum of {max_size} (XXL_JOB_CALLBACK_BATCH_MAX_SIZE); "
                "the batch is never auto-split"
            )

        # 先整体校验并规范化，任何一条失败都不发送。
        # Validate and normalize the whole batch first; send nothing on failure.
        normalized: List[CallbackRequest] = [
            self._normalize_item(index, item) for index, item in enumerate(items)
        ]

        payload = [request.to_wire() for request in normalized]
        return post_to_admins(
            self._config.admin_addresses,
            CALLBACK_PATH,
            payload,
            self._config.access_token,
            self._config.timeout,
            policy=AdminCallPolicy.from_config(self._config),
        )

    def _normalize_item(self, index: int, item: CallbackLike) -> CallbackRequest:
        if isinstance(item, CallbackRequest):
            request = item
        elif isinstance(item, dict):
            try:
                request = CallbackRequest(
                    log_id=item["log_id"],
                    log_date_time=item["log_date_time"],
                    handle_code=item.get("handle_code", 200),
                    handle_msg=_require_str(
                        index, "handle_msg", item.get("handle_msg")
                    ),
                )
            except KeyError as exc:
                raise XXLJobValidationError(
                    f"callback item at index {index} is missing key {exc}"
                ) from exc
        else:
            raise XXLJobValidationError(
                f"callback item at index {index} must be a CallbackRequest or "
                f"dict, got {type(item).__name__}"
            )

        _require_int(index, "log_id", request.log_id)
        _require_int(index, "log_date_time", request.log_date_time)
        _require_int(index, "handle_code", request.handle_code)

        message = _require_str(index, "handle_msg", request.handle_msg)
        max_length = self._config.callback_message_max_length
        if len(message) > max_length:
            message = message[:max_length]

        return CallbackRequest(
            log_id=request.log_id,
            log_date_time=request.log_date_time,
            handle_code=request.handle_code,
            handle_msg=message,
        )


def _require_int(index: int, name: str, value: object) -> None:
    # bool 是 int 的子类，但回调参数不接受布尔值。
    # bool is a subclass of int, but callback arguments reject booleans.
    if isinstance(value, bool) or not isinstance(value, int):
        raise XXLJobValidationError(
            f"callback item at index {index}: {name} must be an integer, got "
            f"{type(value).__name__}"
        )


def _require_str(index: int, name: str, value: object) -> str:
    try:
        return coerce_str(value, name)
    except ModelParseError as exc:
        raise XXLJobValidationError(
            f"callback item at index {index}: {exc}"
        ) from exc

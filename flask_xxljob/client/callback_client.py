"""
XXL-JOB 任务结果回调客户端。

XXL-JOB task-result callback client.
"""

from __future__ import annotations

from ..config import XXLJobConfig
from ..model.callback import CallbackRequest
from . import CallResult, post_to_admins

# 官方 Admin 回调接口路径 / Official admin callback API path.
CALLBACK_PATH = "/api/callback"


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
        handle_msg: str = "",
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
        message = handle_msg or ""
        max_length = self._config.callback_message_max_length
        if len(message) > max_length:
            message = message[:max_length]

        request = CallbackRequest(
            log_id=log_id,
            log_date_time=log_date_time,
            handle_code=handle_code,
            handle_msg=message,
        )

        return post_to_admins(
            self._config.admin_addresses,
            CALLBACK_PATH,
            [request.to_wire()],
            self._config.access_token,
            self._config.timeout,
            stop_on_business_response=True,
        )

"""
XXL-JOB Admin 注册客户端。

XXL-JOB admin registry client.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..config import XXLJobConfig
from ..model.registry import RegistryRequest
from . import CallResult, post_to_admins
from .policy import AdminCallPolicy

# 官方 Admin 注册接口路径 / Official admin registry API paths.
REGISTRY_PATH = "/api/registry"
REGISTRY_REMOVE_PATH = "/api/registryRemove"


class AdminClient:
    """
    调用官方 ``/api/registry`` 与 ``/api/registryRemove`` 接口。

    支持多个 Admin 地址，当前地址失败时自动尝试下一个。

    Calls the official ``/api/registry`` and ``/api/registryRemove`` APIs.

    Supports multiple admin addresses and automatically tries the next one
    when the current address fails.
    """

    def __init__(
        self,
        config: XXLJobConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._config = config
        self._logger = logger

    def registry(self, request: RegistryRequest) -> CallResult:
        """
        调用 ``/api/registry`` 注册或续约执行器。

        Call ``/api/registry`` to register or renew the executor.
        """
        return post_to_admins(
            self._config.admin_addresses,
            REGISTRY_PATH,
            request.to_wire(),
            self._config.access_token,
            self._config.timeout,
            policy=AdminCallPolicy.from_config(self._config),
            logger=self._logger,
        )

    def registry_remove(self, request: RegistryRequest) -> CallResult:
        """
        调用 ``/api/registryRemove`` 注销执行器。

        Call ``/api/registryRemove`` to deregister the executor.
        """
        return post_to_admins(
            self._config.admin_addresses,
            REGISTRY_REMOVE_PATH,
            request.to_wire(),
            self._config.access_token,
            self._config.timeout,
            policy=AdminCallPolicy.from_config(self._config),
            logger=self._logger,
        )

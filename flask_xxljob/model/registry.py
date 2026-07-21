"""
XXL-JOB ``/api/registry`` 与 ``/api/registryRemove`` 请求模型。

XXL-JOB ``/api/registry`` and ``/api/registryRemove`` request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# 官方执行器注册分组常量 / Official executor registry group constant.
REGISTRY_GROUP_EXECUTOR = "EXECUTOR"


@dataclass
class RegistryRequest:
    """
    官方 ``RegistryParam`` 的类型化 Python 表示。

    执行器注册时 ``registry_group`` 固定为 ``"EXECUTOR"``，``registry_key``
    为执行器应用名称，``registry_value`` 为执行器地址。

    A typed Python representation of the official ``RegistryParam``.

    For executor registration ``registry_group`` is fixed to ``"EXECUTOR"``,
    ``registry_key`` is the executor application name and ``registry_value``
    is the executor address.
    """

    registry_group: str = REGISTRY_GROUP_EXECUTOR
    registry_key: str = ""
    registry_value: str = ""

    @classmethod
    def for_executor(cls, app_name: str, address: str) -> "RegistryRequest":
        """
        构造执行器注册请求。

        Build an executor registration request.
        """
        return cls(
            registry_group=REGISTRY_GROUP_EXECUTOR,
            registry_key=app_name,
            registry_value=address,
        )

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "RegistryRequest":
        """
        从官方 ``RegistryParam`` JSON 字典构造对象。

        Build the object from an official ``RegistryParam`` JSON mapping.
        """
        return cls(
            registry_group=data.get("registryGroup") or REGISTRY_GROUP_EXECUTOR,
            registry_key=data.get("registryKey") or "",
            registry_value=data.get("registryValue") or "",
        )

    def to_wire(self) -> dict:
        """
        转换为官方 ``RegistryParam`` JSON 字典。

        Convert to an official ``RegistryParam`` JSON mapping.
        """
        return {
            "registryGroup": self.registry_group,
            "registryKey": self.registry_key,
            "registryValue": self.registry_value,
        }

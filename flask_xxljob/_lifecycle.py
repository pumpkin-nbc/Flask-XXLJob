"""Internal executor-registration lifecycle helpers."""

from __future__ import annotations

import weakref

from flask import Flask

from .registry.registry_service import RegistryService
from .runtime import XXLJobRuntime


def start_registry_with_shutdown(registry_service: RegistryService) -> None:
    """Start a service; the owning runtime finalizer performs cleanup."""
    registry_service.start()


def safe_stop_registry(registry_service: RegistryService) -> None:
    """Stop quietly during interpreter teardown."""
    try:
        registry_service.stop()
    except Exception:  # noqa: BLE001 - interpreter shutdown must remain quiet
        pass


def install_runtime_finalizer(
    app: Flask, runtime: XXLJobRuntime
) -> "weakref.finalize":
    """Close a runtime when its Flask app is collected or at process exit."""
    return weakref.finalize(app, safe_close_runtime, runtime)


def safe_close_runtime(runtime: XXLJobRuntime) -> None:
    """Close quietly during garbage collection or interpreter teardown."""
    try:
        runtime.close()
    except Exception:  # noqa: BLE001 - interpreter shutdown must remain quiet
        pass

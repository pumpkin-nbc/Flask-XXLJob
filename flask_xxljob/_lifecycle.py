"""Internal executor-registration lifecycle helpers."""

from __future__ import annotations

import atexit
import os

from flask import Flask

from .registry.registry_service import RegistryService


def should_start_registry(app: Flask) -> bool:
    """Avoid starting the registry thread in the debug reloader parent."""
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        return True
    return not app.debug


def start_registry_with_shutdown(registry_service: RegistryService) -> None:
    """Start a service and arrange best-effort process-exit cleanup."""
    registry_service.start()
    atexit.register(safe_stop_registry, registry_service)


def safe_stop_registry(registry_service: RegistryService) -> None:
    """Stop quietly during interpreter teardown."""
    try:
        registry_service.stop()
    except Exception:  # noqa: BLE001 - interpreter shutdown must remain quiet
        pass

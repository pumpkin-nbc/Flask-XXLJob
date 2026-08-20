"""Internal Flask application and route helpers."""

from __future__ import annotations

import threading
import weakref
from typing import Iterable, Optional

from flask import Flask

from .exceptions import XXLJobError, XXLJobInitializationError

EXECUTOR_ROUTE_SUFFIXES = ("/beat", "/idleBeat", "/run", "/kill", "/log")


def executor_paths(route_prefix: str) -> frozenset[str]:
    """Return the executor paths mounted below a normalized prefix."""
    prefix = route_prefix or ""
    return frozenset(prefix + suffix for suffix in EXECUTOR_ROUTE_SUFFIXES)


def ensure_executor_routes_available(app: Flask, route_prefix: str) -> None:
    """Fail when a host POST route would shadow an executor endpoint."""
    paths = executor_paths(route_prefix)
    conflicts = sorted(
        {
            rule.rule
            for rule in app.url_map.iter_rules()
            if rule.rule in paths and "POST" in (rule.methods or set())
        }
    )
    if conflicts:
        rendered = ", ".join(conflicts)
        raise XXLJobInitializationError(
            "Flask-XXLJob executor route conflict for POST: "
            f"{rendered}. Configure XXL_JOB_ROUTE_PREFIX or remove the host route."
        )


def ensure_blueprint_name_available(app: Flask, name: str) -> None:
    """Fail before commit when the executor Blueprint name is already used."""
    if name in app.blueprints:
        raise XXLJobInitializationError(
            "Flask-XXLJob blueprint name conflict: "
            f"{name}. Remove the host blueprint with that name before init_app()."
        )


class ApplicationRegistry:
    """Track initialized applications without retaining them indefinitely."""

    def __init__(self) -> None:
        self._apps: weakref.WeakSet[Flask] = weakref.WeakSet()
        self._lock = threading.RLock()

    def add(self, app: Flask) -> None:
        with self._lock:
            self._apps.add(app)

    def discard(self, app: Flask) -> None:
        """Forget an application if it is currently tracked."""
        with self._lock:
            self._apps.discard(app)

    def snapshot(self) -> Iterable[Flask]:
        with self._lock:
            return tuple(self._apps)

    def resolve(self, app: Optional[Flask] = None) -> Flask:
        if app is not None:
            return app
        apps = tuple(self.snapshot())
        if not apps:
            raise XXLJobError(
                "No Flask application available. Pass app=... or run within an "
                "application context."
            )
        if len(apps) > 1:
            raise XXLJobError(
                "Multiple Flask applications are initialized. Pass app=... or run "
                "within the target application's context."
            )
        return apps[0]

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return not self._apps

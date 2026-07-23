"""Internal application and registry lifecycle helper tests."""

from __future__ import annotations

from flask import Flask

from flask_xxljob._app import ApplicationRegistry
from flask_xxljob._lifecycle import (
    safe_stop_registry,
    should_start_registry,
    start_registry_with_shutdown,
)


def test_application_registry_explicit_app_wins():
    registry = ApplicationRegistry()
    explicit = Flask("explicit")
    assert registry.resolve(explicit) is explicit


def test_registry_start_respects_debug_reloader(monkeypatch):
    app = Flask("lifecycle")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)

    app.debug = False
    assert should_start_registry(app) is True
    app.debug = True
    assert should_start_registry(app) is False

    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    assert should_start_registry(app) is True


def test_start_registry_registers_shutdown_hook(mocker):
    service = mocker.Mock()
    register = mocker.patch("flask_xxljob._lifecycle.atexit.register")

    start_registry_with_shutdown(service)

    service.start.assert_called_once_with()
    register.assert_called_once_with(safe_stop_registry, service)


def test_safe_stop_registry_swallows_shutdown_errors(mocker):
    service = mocker.Mock()
    service.stop.side_effect = RuntimeError("shutdown")

    safe_stop_registry(service)

    service.stop.assert_called_once_with()

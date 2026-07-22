"""Public exception-hierarchy tests (0.2.0)."""

from __future__ import annotations

import flask_xxljob
from flask_xxljob.exceptions import (
    FlaskXXLJobError,
    XXLJobAdminCallError,
    XXLJobAlreadyInitializedError,
    XXLJobCallbackError,
    XXLJobCallbackRegistrationError,
    XXLJobConfigError,
    XXLJobConfigurationError,
    XXLJobError,
    XXLJobInitializationError,
    XXLJobRegistryError,
    XXLJobRequestError,
    XXLJobValidationError,
)


def test_base_alias():
    assert XXLJobError is FlaskXXLJobError
    assert issubclass(FlaskXXLJobError, Exception)


def test_config_aliases():
    assert XXLJobConfigError is XXLJobConfigurationError
    assert issubclass(XXLJobConfigurationError, FlaskXXLJobError)


def test_validation_aliases():
    assert XXLJobRequestError is XXLJobValidationError
    assert issubclass(XXLJobValidationError, FlaskXXLJobError)


def test_initialization_hierarchy():
    assert issubclass(XXLJobInitializationError, FlaskXXLJobError)
    assert issubclass(XXLJobAlreadyInitializedError, XXLJobInitializationError)


def test_admin_call_hierarchy():
    assert issubclass(XXLJobAdminCallError, FlaskXXLJobError)
    assert issubclass(XXLJobCallbackError, XXLJobAdminCallError)
    assert issubclass(XXLJobRegistryError, XXLJobAdminCallError)


def test_callback_registration_error():
    assert issubclass(XXLJobCallbackRegistrationError, FlaskXXLJobError)


def test_all_public_exceptions_catchable_as_base():
    for exc_cls in (
        XXLJobConfigurationError,
        XXLJobInitializationError,
        XXLJobAlreadyInitializedError,
        XXLJobCallbackRegistrationError,
        XXLJobValidationError,
        XXLJobAdminCallError,
        XXLJobCallbackError,
        XXLJobRegistryError,
    ):
        try:
            raise exc_cls("boom")
        except FlaskXXLJobError:
            pass


def test_exceptions_exported_from_package():
    for name in (
        "FlaskXXLJobError",
        "XXLJobError",
        "XXLJobConfigError",
        "XXLJobConfigurationError",
        "XXLJobInitializationError",
        "XXLJobAlreadyInitializedError",
        "XXLJobCallbackRegistrationError",
        "XXLJobValidationError",
        "XXLJobRequestError",
        "XXLJobAdminCallError",
        "XXLJobCallbackError",
        "XXLJobRegistryError",
    ):
        assert name in flask_xxljob.__all__
        assert hasattr(flask_xxljob, name)

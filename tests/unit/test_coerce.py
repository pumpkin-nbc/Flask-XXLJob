"""Numeric coercion tests for protocol-model fields (0.1.1)."""

from __future__ import annotations

import pytest

from flask_xxljob.model.coerce import ModelParseError, coerce_int


def test_missing_returns_default():
    assert coerce_int(None, "jobId") == 0
    assert coerce_int(None, "jobId", default=7) == 7


def test_zero_is_preserved():
    # 0 不能被当作空值。 / 0 must not be treated as empty.
    assert coerce_int(0, "jobId") == 0


def test_valid_int_and_numeric_string():
    assert coerce_int(5, "jobId") == 5
    assert coerce_int("42", "jobId") == 42
    assert coerce_int("  8  ", "jobId") == 8


def test_blank_string_returns_default():
    assert coerce_int("", "jobId") == 0
    assert coerce_int("   ", "jobId") == 0


def test_integral_float_ok_fractional_rejected():
    assert coerce_int(3.0, "jobId") == 3
    with pytest.raises(ModelParseError):
        coerce_int(3.5, "jobId")


def test_non_numeric_string_raises():
    with pytest.raises(ModelParseError):
        coerce_int("abc", "jobId")


def test_bool_rejected():
    with pytest.raises(ModelParseError):
        coerce_int(True, "jobId")
    with pytest.raises(ModelParseError):
        coerce_int(False, "jobId")

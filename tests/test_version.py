"""Package version tests."""

from __future__ import annotations

import flask_xxljob
from flask_xxljob._version import __version__ as source_version


def test_version_is_0_3_0():
    assert source_version == "0.3.0"
    assert flask_xxljob.__version__ == source_version

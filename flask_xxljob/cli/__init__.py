"""
Flask-XXLJob 命令行接口。

Flask-XXLJob command-line interface.
"""

from __future__ import annotations

from .commands import main, xxljob_cli

__all__ = ["xxljob_cli", "main"]

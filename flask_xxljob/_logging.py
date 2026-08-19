"""Per-application logging management for Flask-XXLJob."""

from __future__ import annotations

import itertools
import logging
import re
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional

from flask import Flask

from .config import XXLJobConfig
from .exceptions import XXLJobInitializationError

_RUNTIME_IDS = itertools.count(1)
_RUNTIME_IDS_LOCK = threading.Lock()
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(authorization|cookie|password|xxl-job-access-token|"
    r"executorParams|glueSource|handleMsg)\b\s*[:=]\s*([^\r\n,;]+)"
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)
_LEVEL_COLORS = {
    "DEBUG": "\033[34m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_COLOR_RESET = "\033[0m"


def _next_runtime_id() -> int:
    with _RUNTIME_IDS_LOCK:
        return next(_RUNTIME_IDS)


def _safe_app_name(name: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._-")
    return rendered or "app"


def redact_text(value: object, access_token: str = "") -> str:
    """Return a bounded, best-effort redaction of plugin diagnostic text."""
    text = str(value)
    if access_token:
        text = text.replace(access_token, "<redacted>")
    text = _PRIVATE_KEY.sub("<redacted-private-key>", text)
    return _SENSITIVE_ASSIGNMENT.sub(r"\1=<redacted>", text)


class SensitiveDataFilter(logging.Filter):
    """Redact known secrets before a record reaches a managed handler."""

    def __init__(self, access_token: str) -> None:
        super().__init__()
        self._access_token = access_token

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage(), self._access_token)
        record.args = ()
        # Preserve traceback data.  The filter redacts plugin-authored message
        # fields; application code remains responsible for not placing secrets
        # directly in exception messages.
        return True


class LevelColorFormatter(logging.Formatter):
    """Color a complete console record according to its standard level."""

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        color = _LEVEL_COLORS.get(record.levelname)
        if color is None:
            return rendered
        return f"{color}{rendered}{_COLOR_RESET}"


class XXLJobLogManager:
    """Own the managed handlers for one Flask application runtime."""

    def __init__(self, app: Flask, config: XXLJobConfig) -> None:
        runtime_id = _next_runtime_id()
        self.name = (
            f"flask_xxljob.app.{_safe_app_name(app.name)}.{runtime_id}"
        )
        self.logger = logging.getLogger(self.name)
        self._config = config
        self._lock = threading.RLock()
        self._handlers: List[logging.Handler] = []
        self._closed = False
        self._original_level = self.logger.level
        self._original_propagate = self.logger.propagate
        self._log_file: Optional[str] = None
        self._configure()

    def _configure(self) -> None:
        if not self.effective_enabled:
            return
        if not (
            self._config.log_file_enabled or self._config.log_console_enabled
        ):
            return

        file_formatter = logging.Formatter(
            self._config.log_format,
            self._config.log_date_format or None,
        )
        console_formatter = LevelColorFormatter(
            self._config.log_format,
            self._config.log_date_format or None,
        )
        level = getattr(logging, self._config.log_level)
        created: List[logging.Handler] = []
        try:
            if self._config.log_file_enabled:
                directory = Path(self._config.log_path).expanduser().resolve()
                directory.mkdir(parents=True, exist_ok=True)
                path = (directory / self._config.log_filename).resolve()
                file_handler = RotatingFileHandler(
                    str(path),
                    maxBytes=self._config.log_max_bytes,
                    backupCount=self._config.log_backup_count,
                    encoding=self._config.log_encoding,
                )
                self._prepare_handler(
                    file_handler, "file", level, file_formatter
                )
                created.append(file_handler)
                self._log_file = str(path)

            if self._config.log_console_enabled:
                console_handler = logging.StreamHandler()
                self._prepare_handler(
                    console_handler, "console", level, console_formatter
                )
                created.append(console_handler)
        except Exception as exc:
            for handler in created:
                handler.close()
            raise XXLJobInitializationError(
                "Failed to initialize Flask-XXLJob logging "
                f"({type(exc).__name__})."
            ) from exc

        self.logger.setLevel(level)
        self.logger.propagate = self._config.log_propagate
        for handler in created:
            self.logger.addHandler(handler)
        self._handlers = created

    def _prepare_handler(
        self,
        handler: logging.Handler,
        handler_type: str,
        level: int,
        formatter: logging.Formatter,
    ) -> None:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter(self._config.access_token))
        handler._flask_xxljob_managed = True  # type: ignore[attr-defined]
        handler._flask_xxljob_handler_type = handler_type  # type: ignore[attr-defined]
        handler._flask_xxljob_owner = self.name  # type: ignore[attr-defined]

    @property
    def effective_enabled(self) -> bool:
        return self._config.enabled and self._config.log_enabled

    @property
    def file_enabled(self) -> bool:
        return self.effective_enabled and self._config.log_file_enabled

    @property
    def console_enabled(self) -> bool:
        return self.effective_enabled and self._config.log_console_enabled

    @property
    def log_file(self) -> Optional[str]:
        return self._log_file if self.file_enabled else None

    @property
    def level(self) -> str:
        return self._config.log_level

    @property
    def managed_handlers(self) -> tuple:
        return tuple(self._handlers)

    def get_logger(self, component: str) -> logging.Logger:
        return logging.getLogger(f"{self.name}.{component}")

    def prepare_shutdown(self) -> None:
        """Detach managed handlers whose streams are already unavailable."""
        with self._lock:
            available: List[logging.Handler] = []
            for handler in self._handlers:
                stream = getattr(handler, "stream", None)
                if stream is not None and getattr(stream, "closed", False):
                    self.logger.removeHandler(handler)
                    try:
                        handler.close()
                    except (OSError, ValueError):
                        pass
                else:
                    available.append(handler)
            self._handlers = available

    def close(self) -> None:
        """Flush, remove and close only handlers owned by this runtime."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for handler in tuple(self._handlers):
                self.logger.removeHandler(handler)
                try:
                    handler.flush()
                except (OSError, ValueError):
                    pass
                try:
                    handler.close()
                except (OSError, ValueError):
                    pass
            self._handlers.clear()
            self.logger.setLevel(self._original_level)
            self.logger.propagate = self._original_propagate


__all__ = [
    "LevelColorFormatter",
    "SensitiveDataFilter",
    "XXLJobLogManager",
    "redact_text",
]

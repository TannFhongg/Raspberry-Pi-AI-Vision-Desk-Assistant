"""Shared logging bootstrap for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import DeviceSettings, load_device_settings

APP_LOG_HANDLER_NAME = "vision-app-log"
ERROR_LOG_HANDLER_NAME = "vision-error-log"
STREAM_HANDLER_NAME = "vision-stream-log"
MANAGED_HANDLER_NAMES = {
    APP_LOG_HANDLER_NAME,
    ERROR_LOG_HANDLER_NAME,
    STREAM_HANDLER_NAME,
}
_EXCEPTION_HOOKS_INSTALLED = False
_ORIGINAL_SYS_EXCEPTHOOK = sys.excepthook
_ORIGINAL_THREAD_EXCEPTHOOK = threading.excepthook


def configure_logging(
    settings: DeviceSettings | None = None,
    logs_dir: str | Path = "logs",
) -> logging.Logger:
    """Configure root logging for file rotation plus console output."""
    resolved_settings = settings or load_device_settings()
    reliability = getattr(resolved_settings, "reliability", None)
    if reliability is None:
        reliability = load_device_settings().reliability
    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)

    configured_level = getattr(logging, reliability.log_level, logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(configured_level)
    _remove_managed_handlers(root_logger)

    app_handler = RotatingFileHandler(
        directory / "app.log",
        maxBytes=reliability.log_max_bytes,
        backupCount=reliability.log_backup_count,
        encoding="utf-8",
    )
    app_handler.set_name(APP_LOG_HANDLER_NAME)
    app_handler.setLevel(configured_level)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        directory / "error.log",
        maxBytes=reliability.log_max_bytes,
        backupCount=reliability.log_backup_count,
        encoding="utf-8",
    )
    error_handler.set_name(ERROR_LOG_HANDLER_NAME)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.set_name(STREAM_HANDLER_NAME)
    stream_handler.setLevel(configured_level)
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(stream_handler)

    _install_exception_hooks()
    return logging.getLogger(__name__)


def _remove_managed_handlers(root_logger: logging.Logger) -> None:
    """Remove and close handlers previously installed by this module."""
    for handler in list(root_logger.handlers):
        if handler.get_name() not in MANAGED_HANDLER_NAMES:
            continue
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def _install_exception_hooks() -> None:
    """Log otherwise uncaught process and background-thread exceptions."""
    global _EXCEPTION_HOOKS_INSTALLED

    if _EXCEPTION_HOOKS_INSTALLED:
        return

    def handle_sys_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger(__name__).critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc_value, exc_traceback)

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is not None and issubclass(args.exc_type, KeyboardInterrupt):
            _ORIGINAL_THREAD_EXCEPTHOOK(args)
            return
        logging.getLogger(__name__).critical(
            "Uncaught thread exception in %s",
            getattr(args.thread, "name", "unknown-thread"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        _ORIGINAL_THREAD_EXCEPTHOOK(args)

    sys.excepthook = handle_sys_exception
    threading.excepthook = handle_thread_exception
    _EXCEPTION_HOOKS_INSTALLED = True

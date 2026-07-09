"""Unit tests for the Phase 14 logging bootstrap."""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from system.logging import MANAGED_HANDLER_NAMES, configure_logging


class LoggingBootstrapTests(unittest.TestCase):
    """Verify rotating file logging and idempotent bootstrap behavior."""

    def test_configure_logging_creates_app_and_error_logs(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-logging-test-"))
        logs_dir = temp_dir / "logs"

        configure_logging(settings=_build_settings(), logs_dir=logs_dir)
        logger = logging.getLogger("tests.logging")
        logger.info("info line")
        logger.error("error line")
        _flush_handlers()

        app_log = (logs_dir / "app.log").read_text(encoding="utf-8")
        error_log = (logs_dir / "error.log").read_text(encoding="utf-8")

        self.assertIn("info line", app_log)
        self.assertIn("error line", app_log)
        self.assertIn("error line", error_log)
        self.assertNotIn("info line", error_log)

    def test_configure_logging_is_idempotent(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-logging-repeat-"))
        logs_dir = temp_dir / "logs"

        configure_logging(settings=_build_settings(), logs_dir=logs_dir)
        configure_logging(settings=_build_settings(), logs_dir=logs_dir)

        managed_handlers = [
            handler.get_name()
            for handler in logging.getLogger().handlers
            if handler.get_name() in MANAGED_HANDLER_NAMES
        ]
        self.assertEqual(sorted(managed_handlers), sorted(MANAGED_HANDLER_NAMES))


def _build_settings() -> SimpleNamespace:
    """Return a small settings object with only the needed reliability fields."""
    return SimpleNamespace(
        reliability=SimpleNamespace(
            log_level="INFO",
            log_max_bytes=1_048_576,
            log_backup_count=5,
        )
    )


def _flush_handlers() -> None:
    """Flush root logging handlers so test file reads see all log lines."""
    for handler in logging.getLogger().handlers:
        if hasattr(handler, "flush"):
            handler.flush()

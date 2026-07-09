"""Unit tests for the production systemd service template."""

from __future__ import annotations

import unittest
from pathlib import Path


class DeploymentServiceTemplateTests(unittest.TestCase):
    """Verify the service template keeps the app alive after crashes."""

    def test_service_file_enables_auto_restart(self) -> None:
        service_text = Path("deployment/ai-vision-assistant.service").read_text(encoding="utf-8")

        self.assertIn("StartLimitIntervalSec=0", service_text)
        self.assertIn("Restart=always", service_text)
        self.assertIn("RestartSec=3", service_text)

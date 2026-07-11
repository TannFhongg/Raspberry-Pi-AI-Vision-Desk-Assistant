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

    def test_kiosk_launcher_defaults_to_localhost_loopback(self) -> None:
        launcher_text = Path("deployment/kiosk-launch.sh").read_text(encoding="utf-8")

        self.assertIn('APP_URL="${STARTUP_URL:-http://127.0.0.1:5000}"', launcher_text)

    def test_env_example_uses_local_only_defaults(self) -> None:
        env_text = Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("APP_HOST=127.0.0.1", env_text)
        self.assertIn("APP_PORT=5000", env_text)
        self.assertIn("STARTUP_URL=http://127.0.0.1:5000", env_text)
        self.assertIn("STORE_IMAGES=0", env_text)

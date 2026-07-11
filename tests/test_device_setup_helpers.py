"""Unit tests for first-boot setup helper functions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from system.device_setup import connect_wifi_network, scan_wifi_networks, upsert_env_value


class EnvFileUpsertTests(unittest.TestCase):
    """Verify `.env` updates preserve surrounding content."""

    def test_upsert_env_value_preserves_comments_and_other_keys(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="env-upsert-test-"))
        env_path = temp_dir / ".env"
        env_path.write_text(
            "# Existing comment\nOPENAI_API_KEY=old-value\nFLASK_DEBUG=0\n",
            encoding="utf-8",
        )

        upsert_env_value(env_path, "OPENAI_API_KEY", "new-value")

        self.assertEqual(
            env_path.read_text(encoding="utf-8"),
            "# Existing comment\nOPENAI_API_KEY=new-value\nFLASK_DEBUG=0\n",
        )


class WifiNmcliHelperTests(unittest.TestCase):
    """Verify nmcli parsing and connection command behavior."""

    def test_scan_wifi_networks_deduplicates_and_sorts(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="\n".join(
                [
                    "Guest:40:open",
                    "Office:80:WPA2",
                    "Office:55:WPA2",
                    "Lab\\:SSID:65:WPA3",
                ]
            ),
            stderr="",
        )

        networks = scan_wifi_networks(
            runner=lambda *args, **kwargs: completed,
        )

        self.assertEqual([network["ssid"] for network in networks], ["Office", "Lab\\:SSID", "Guest"])
        self.assertEqual(networks[0]["signal"], 80)

    def test_connect_wifi_network_sets_autoconnect(self) -> None:
        commands: list[list[str]] = []

        def fake_runner(command, **kwargs):
            commands.append(command)
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        result = connect_wifi_network(
            ssid="Office",
            password="topsecret",
            connection_name="Office",
            hidden=True,
            auto_connect=True,
            runner=fake_runner,
        )

        self.assertEqual(result["ssid"], "Office")
        self.assertEqual(result["connection_name"], "Office")
        self.assertEqual(
            commands[0],
            ["nmcli", "device", "wifi", "connect", "Office", "password", "topsecret", "name", "Office", "hidden", "yes"],
        )
        self.assertEqual(
            commands[1],
            ["nmcli", "connection", "modify", "Office", "connection.autoconnect", "yes"],
        )

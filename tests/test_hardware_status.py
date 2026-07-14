"""Unit tests for shared device-state helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hardware.status import (
    DeviceState,
    build_ready_state_payload,
    build_ui_state_payload,
    clear_latest_result_file,
    is_busy_device_state,
    screen_for_device_state,
)


class DeviceStatusHelperTests(unittest.TestCase):
    """Verify state-to-UI mappings and cleared-result persistence."""

    def test_ready_payload_maps_to_home_screen(self) -> None:
        payload = build_ready_state_payload(
            selected_mode="",
            ready_detail="Press button to select the mode.",
        )

        self.assertEqual(payload["device_state"], "READY")
        self.assertEqual(payload["screen"], "home")
        self.assertEqual(payload["status"], "Ready")
        self.assertEqual(payload["detail"], "Press button to select the mode.")
        self.assertEqual(payload["current_step"], -1)
        self.assertEqual(payload["progress_state"], "IDLE")

    def test_mode_selected_payload_stays_on_home_screen(self) -> None:
        payload = build_ui_state_payload(
            DeviceState.MODE_SELECTED,
            selected_mode="solve_problem",
            ready_detail="Press button to select the mode.",
            detail="Selected mode ready. Press Button Main to capture.",
        )

        self.assertEqual(payload["device_state"], "MODE_SELECTED")
        self.assertEqual(payload["screen"], "home")
        self.assertEqual(payload["status"], "Mode Selected")
        self.assertEqual(payload["detail"], "Selected mode ready. Press Button Main to capture.")

    def test_done_payload_maps_answer_to_result_screen(self) -> None:
        payload = build_ui_state_payload(
            DeviceState.DONE,
            selected_mode="solve_problem",
            ready_detail="Ready",
            answer="Answer ready",
            current_step=3,
        )

        self.assertEqual(payload["device_state"], "DONE")
        self.assertEqual(payload["screen"], "result")
        self.assertEqual(payload["answer"], "Answer ready")
        self.assertEqual(payload["error"], "")
        self.assertEqual(payload["progress_state"], "DONE")

    def test_error_payload_maps_error_to_error_screen(self) -> None:
        payload = build_ui_state_payload(
            DeviceState.ERROR,
            selected_mode="solve_problem",
            ready_detail="Ready",
            error="Camera not found",
            error_detail="Camera backend failed",
        )

        self.assertEqual(payload["device_state"], "ERROR")
        self.assertEqual(payload["screen"], "error")
        self.assertEqual(payload["error"], "Camera not found")
        self.assertEqual(payload["error_detail"], "Camera backend failed")
        self.assertEqual(payload["progress_state"], "ERROR")

    def test_busy_state_helper_recognizes_capture_and_processing(self) -> None:
        self.assertTrue(is_busy_device_state(DeviceState.CAPTURING))
        self.assertTrue(is_busy_device_state("PROCESSING"))
        self.assertFalse(is_busy_device_state(DeviceState.DONE))
        self.assertFalse(is_busy_device_state(DeviceState.MODE_SELECTED))
        self.assertEqual(screen_for_device_state("MODE_SELECTED"), "home")
        self.assertEqual(screen_for_device_state("READY"), "home")

    def test_clear_latest_result_file_writes_readable_placeholder(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="hardware-status-test-"))
        result_path = temp_dir / "latest_result.txt"

        clear_latest_result_file(result_path, mode="solve_problem")
        contents = result_path.read_text(encoding="utf-8")

        self.assertIn("Status: cleared", contents)
        self.assertIn("Mode: solve_problem", contents)
        self.assertIn("Message: No result available", contents)

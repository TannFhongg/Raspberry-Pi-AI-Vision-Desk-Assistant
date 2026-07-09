"""Unit tests for shared pipeline preprocessing decisions and freshness metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.runner import is_processed_fresh, should_use_screen_optimization
from vision.preprocess import build_preprocess_metadata, write_preprocess_metadata


class ScreenOptimizationResolutionTests(unittest.TestCase):
    """Verify auto/on/off screen optimization behavior by mode."""

    def test_auto_enables_screen_optimization_for_text_modes(self) -> None:
        self.assertTrue(should_use_screen_optimization("document_reader", "auto"))
        self.assertTrue(should_use_screen_optimization("math_solver", "auto"))
        self.assertTrue(should_use_screen_optimization("meeting_assistant", "auto"))
        self.assertFalse(should_use_screen_optimization("engineering_mode", "auto"))
        self.assertFalse(should_use_screen_optimization("general_vision", "auto"))

    def test_legacy_aliases_still_normalize_for_auto_screen_optimization(self) -> None:
        self.assertTrue(should_use_screen_optimization("read_text", "auto"))
        self.assertTrue(should_use_screen_optimization("summarize_document", "auto"))
        self.assertTrue(should_use_screen_optimization("solve_problem", "auto"))
        self.assertFalse(should_use_screen_optimization("professional_assistant", "auto"))

    def test_on_forces_screen_optimization_for_all_modes(self) -> None:
        self.assertTrue(should_use_screen_optimization("engineering_mode", "on"))
        self.assertTrue(should_use_screen_optimization("general_vision", "on"))

    def test_off_disables_screen_optimization_for_all_modes(self) -> None:
        self.assertFalse(should_use_screen_optimization("document_reader", "off"))
        self.assertFalse(should_use_screen_optimization("general_vision", "off"))

    def test_invalid_screen_optimization_setting_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            should_use_screen_optimization("document_reader", "sometimes")


class ProcessedFreshnessTests(unittest.TestCase):
    """Verify metadata-based freshness checks for processed images."""

    def test_processed_image_is_fresh_when_metadata_matches(self) -> None:
        captured_path, processed_path = _create_source_and_output_files()
        write_preprocess_metadata(
            processed_path,
            build_preprocess_metadata(
                input_path=captured_path,
                grayscale=False,
                max_dimension=1600,
                detect_screen=True,
                enhance_text=True,
            ),
        )

        self.assertTrue(
            is_processed_fresh(
                captured_path,
                processed_path,
                grayscale=False,
                max_dimension=1600,
                detect_screen=True,
                enhance_text=True,
            )
        )

    def test_processed_image_is_stale_when_preprocess_options_change(self) -> None:
        captured_path, processed_path = _create_source_and_output_files()
        write_preprocess_metadata(
            processed_path,
            build_preprocess_metadata(
                input_path=captured_path,
                grayscale=False,
                max_dimension=1600,
                detect_screen=True,
                enhance_text=True,
            ),
        )

        stale_cases = (
            {"grayscale": True, "max_dimension": 1600, "detect_screen": True, "enhance_text": True},
            {"grayscale": False, "max_dimension": 1200, "detect_screen": True, "enhance_text": True},
            {"grayscale": False, "max_dimension": 1600, "detect_screen": False, "enhance_text": True},
            {"grayscale": False, "max_dimension": 1600, "detect_screen": True, "enhance_text": False},
            {"grayscale": False, "max_dimension": 1600, "detect_screen": False, "enhance_text": False},
        )

        for case in stale_cases:
            with self.subTest(case=case):
                self.assertFalse(is_processed_fresh(captured_path, processed_path, **case))

    def test_processed_image_is_stale_without_metadata(self) -> None:
        captured_path, processed_path = _create_source_and_output_files()
        self.assertFalse(
            is_processed_fresh(
                captured_path,
                processed_path,
                grayscale=False,
                max_dimension=1600,
                detect_screen=True,
                enhance_text=True,
            )
        )


def _create_source_and_output_files() -> tuple[Path, Path]:
    """Create dummy source and processed files for metadata freshness tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="pipeline-runner-test-"))
    captured_path = temp_dir / "captured.jpg"
    processed_path = temp_dir / "processed.jpg"
    captured_path.write_bytes(b"capture")
    processed_path.write_bytes(b"processed")
    return captured_path, processed_path

"""Unit tests for shared pipeline preprocessing decisions and freshness metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.runner import (
    PipelineResult,
    is_processed_fresh,
    run_capture_analyze,
    should_use_screen_optimization,
)
from vision.preprocess import build_preprocess_metadata, write_preprocess_metadata


class ScreenOptimizationResolutionTests(unittest.TestCase):
    """Verify auto/on/off screen optimization behavior by mode."""

    def test_auto_enables_screen_optimization_for_text_modes(self) -> None:
        self.assertTrue(should_use_screen_optimization("read_text", "auto"))
        self.assertTrue(should_use_screen_optimization("summarize_document", "auto"))
        self.assertTrue(should_use_screen_optimization("professional_assistant", "auto"))
        self.assertTrue(should_use_screen_optimization("solve_problem", "auto"))
        self.assertFalse(should_use_screen_optimization("analyze_image", "auto"))

    def test_legacy_modes_still_normalize_for_auto_screen_optimization(self) -> None:
        self.assertTrue(should_use_screen_optimization("document_reader", "auto"))
        self.assertTrue(should_use_screen_optimization("math_solver", "auto"))
        self.assertTrue(should_use_screen_optimization("meeting_assistant", "auto"))
        self.assertFalse(should_use_screen_optimization("engineering_mode", "auto"))

    def test_on_forces_screen_optimization_for_all_modes(self) -> None:
        self.assertTrue(should_use_screen_optimization("analyze_image", "on"))
        self.assertTrue(should_use_screen_optimization("general_vision", "on"))

    def test_off_disables_screen_optimization_for_all_modes(self) -> None:
        self.assertFalse(should_use_screen_optimization("read_text", "off"))
        self.assertFalse(should_use_screen_optimization("general_vision", "off"))

    def test_invalid_screen_optimization_setting_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            should_use_screen_optimization("read_text", "sometimes")


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


class CaptureAnalyzeFlowTests(unittest.TestCase):
    """Verify the full capture flow analyzes the freshly captured image chain."""

    def test_run_capture_analyze_threads_current_capture_into_preprocess_and_ai(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="capture-analyze-flow-test-"))
        captured_path = temp_dir / "captured-current.jpg"
        processed_path = temp_dir / "processed-current.jpg"
        capture_result = PipelineResult(
            captured_path=captured_path,
            processed_path=None,
            answer=None,
            mode="capture",
            camera_backend_used="opencv",
            camera_resolution=(1920, 1080),
            status="success",
        )
        preprocess_result = PipelineResult(
            captured_path=captured_path,
            processed_path=processed_path,
            answer=None,
            mode="preprocess",
            camera_backend_used=None,
            camera_resolution=None,
            status="success",
        )
        analyze_result = PipelineResult(
            captured_path=captured_path,
            processed_path=processed_path,
            answer="Fresh answer",
            mode="document_reader",
            camera_backend_used=None,
            camera_resolution=None,
            status="success",
        )

        with patch("pipeline.runner.run_capture", return_value=capture_result) as run_capture, patch(
            "pipeline.runner.run_preprocess",
            return_value=preprocess_result,
        ) as run_preprocess, patch(
            "pipeline.runner.run_analyze",
            return_value=analyze_result,
        ) as run_analyze:
            result = run_capture_analyze(
                mode="document_reader",
                captured_path=str(captured_path),
                processed_path=str(processed_path),
            )

        self.assertEqual(result.answer, "Fresh answer")
        run_capture.assert_called_once()
        self.assertEqual(run_preprocess.call_args.kwargs["input_path"], str(captured_path))
        self.assertEqual(run_preprocess.call_args.kwargs["output_path"], str(processed_path))
        self.assertEqual(run_analyze.call_args.kwargs["captured_path"], str(captured_path))
        self.assertEqual(run_analyze.call_args.kwargs["processed_path"], str(processed_path))


def _create_source_and_output_files() -> tuple[Path, Path]:
    """Create dummy source and processed files for metadata freshness tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="pipeline-runner-test-"))
    captured_path = temp_dir / "captured.jpg"
    processed_path = temp_dir / "processed.jpg"
    captured_path.write_bytes(b"capture")
    processed_path.write_bytes(b"processed")
    return captured_path, processed_path

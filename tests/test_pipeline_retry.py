"""Unit tests for pipeline retry metadata used by the offline queue."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai.openai_client import VisionClientError
from pipeline.runner import PipelineError, run_analyze


class PipelineRetryMetadataTests(unittest.TestCase):
    """Verify transient AI failures preserve the image context needed for retry."""

    def test_run_analyze_marks_retryable_failures_with_image_paths(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="pipeline-retry-test-"))
        captured_path = temp_dir / "captured.jpg"
        processed_path = temp_dir / "processed.jpg"
        captured_path.write_bytes(b"captured")
        processed_path.write_bytes(b"processed")
        fake_settings = SimpleNamespace(
            camera=SimpleNamespace(grayscale=False, max_dimension=1600),
            vision=SimpleNamespace(screen_optimization="auto"),
        )
        fake_client = SimpleNamespace(
            analyze_image=lambda **_kwargs: _raise_vision_error(
                VisionClientError("network down", retryable=True)
            )
        )

        with patch("pipeline.runner.load_device_settings", return_value=fake_settings), patch(
            "pipeline.runner.is_processed_fresh",
            return_value=True,
        ), patch(
            "ai.openai_client.OpenAIVisionClient",
            return_value=fake_client,
        ):
            with self.assertRaises(PipelineError) as error:
                run_analyze(
                    mode="document_reader",
                    captured_path=str(captured_path),
                    processed_path=str(processed_path),
                )

        self.assertTrue(error.exception.retryable)
        self.assertEqual(error.exception.captured_path, captured_path)
        self.assertEqual(error.exception.processed_path, processed_path)
        self.assertEqual(error.exception.mode, "document_reader")


def _raise_vision_error(error: VisionClientError):
    """Raise the provided vision error inside a lambda-friendly helper."""
    raise error


if __name__ == "__main__":
    unittest.main()

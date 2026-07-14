"""Parser tests for canonical mode handling across CLI entrypoints."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

import main
import test_ai_vision
import test_gpio_button


class ModeParserCompatibilityTests(unittest.TestCase):
    """Verify legacy mode inputs still parse into canonical mode ids."""

    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            camera=SimpleNamespace(
                backend="opencv",
                index=0,
                resolution=SimpleNamespace(width=4608, height=2592),
                grayscale=False,
                autofocus_mode="continuous",
                exposure="auto",
                brightness=0.0,
                capture_delay_seconds=1.0,
                max_dimension=1600,
            ),
            button=SimpleNamespace(pin=17),
            ai=SimpleNamespace(default_mode="read_text"),
            vision=SimpleNamespace(screen_optimization="auto"),
        )

    def test_main_parser_accepts_legacy_mode_alias(self) -> None:
        parser = main.build_parser(self.settings)
        args = parser.parse_args(["--mode", "solve_problem"])

        self.assertEqual(args.mode, "solve_problem")

    def test_openai_test_parser_accepts_legacy_mode_alias(self) -> None:
        parser = test_ai_vision.build_parser()
        args = parser.parse_args(["--image", "test_images/document.jpg", "--mode", "summarize_document"])

        self.assertEqual(args.mode, "summarize_document")

    def test_gpio_parser_accepts_legacy_mode_alias(self) -> None:
        parser = test_gpio_button.build_parser(self.settings)
        args = parser.parse_args(["--mode", "analyze_image"])

        self.assertEqual(args.mode, "analyze_image")

    def test_parsers_migrate_previous_internal_mode_ids(self) -> None:
        parser = main.build_parser(self.settings)
        args = parser.parse_args(["--mode", "document_reader"])

        self.assertEqual(args.mode, "read_text")

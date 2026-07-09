"""Unit tests for hidden backend assistant mode context."""

from __future__ import annotations

import unittest

from ai.context import build_mode_context
from ai.modes import get_available_modes


class AssistantModeContextTests(unittest.TestCase):
    """Verify mode-specific internal instruction building."""

    def test_each_mode_produces_distinct_context(self) -> None:
        contexts = {mode: build_mode_context(mode) for mode in get_available_modes()}

        self.assertEqual(len(set(contexts.values())), len(contexts))

    def test_context_includes_small_screen_guidance(self) -> None:
        context = build_mode_context("document_reader")

        self.assertIn("small standalone screen", context)
        self.assertIn("Use short paragraphs and bullet points when helpful.", context)

    def test_extra_instruction_is_appended(self) -> None:
        context = build_mode_context("engineering_mode", "Focus on dimensions first.")

        self.assertIn("Current assistant mode: Engineering Mode.", context)
        self.assertIn("Additional internal guidance: Focus on dimensions first.", context)


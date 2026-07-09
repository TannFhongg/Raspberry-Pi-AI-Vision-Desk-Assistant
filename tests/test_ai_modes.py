"""Unit tests for the Phase 13 assistant mode registry."""

from __future__ import annotations

import unittest

from ai.modes import get_available_modes, get_mode, get_mode_definitions, normalize_mode


class AssistantModeRegistryTests(unittest.TestCase):
    """Verify canonical modes and legacy alias handling."""

    def test_canonical_modes_are_stable_and_ordered(self) -> None:
        self.assertEqual(
            get_available_modes(),
            [
                "document_reader",
                "math_solver",
                "meeting_assistant",
                "engineering_mode",
                "general_vision",
            ],
        )

    def test_each_mode_has_name_description_and_system_prompt(self) -> None:
        for mode in get_mode_definitions():
            with self.subTest(mode=mode.id):
                self.assertTrue(mode.name)
                self.assertTrue(mode.description)
                self.assertTrue(mode.system_prompt)

    def test_legacy_aliases_normalize_to_canonical_modes(self) -> None:
        alias_cases = {
            "read_text": "document_reader",
            "summarize": "document_reader",
            "summarize_document": "document_reader",
            "solve_problem": "math_solver",
            "analyze_image": "general_vision",
            "professional_assistant": "general_vision",
        }

        for mode_input, expected in alias_cases.items():
            with self.subTest(mode_input=mode_input):
                self.assertEqual(normalize_mode(mode_input), expected)
                self.assertEqual(get_mode(mode_input).id, expected)


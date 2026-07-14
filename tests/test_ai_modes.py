"""Unit tests for the five public assistant workflows."""

from __future__ import annotations

import unittest

from ai.modes import get_available_modes, get_mode, get_mode_definitions, normalize_mode


class AssistantModeRegistryTests(unittest.TestCase):
    """Verify public workflows and compatibility aliases."""

    def test_canonical_modes_are_stable_and_ordered(self) -> None:
        self.assertEqual(
            get_available_modes(),
            [
                "read_text",
                "summarize_document",
                "analyze_image",
                "professional_assistant",
                "solve_problem",
            ],
        )

    def test_each_mode_has_a_complete_distinct_workflow_contract(self) -> None:
        prompts: set[str] = set()
        contracts: set[str] = set()
        profiles: set[str] = set()
        for mode in get_mode_definitions():
            with self.subTest(mode=mode.id):
                self.assertTrue(mode.name)
                self.assertTrue(mode.description)
                self.assertTrue(mode.system_prompt)
                self.assertTrue(mode.output_contract)
                self.assertTrue(mode.processing_profile)
                prompts.add(mode.system_prompt)
                contracts.add(mode.output_contract)
                profiles.add(mode.processing_profile)

        self.assertEqual(len(prompts), len(get_available_modes()))
        self.assertEqual(len(contracts), len(get_available_modes()))
        self.assertEqual(len(profiles), len(get_available_modes()))

    def test_legacy_internal_modes_normalize_to_public_workflows(self) -> None:
        alias_cases = {
            "document_reader": "read_text",
            "math_solver": "solve_problem",
            "meeting_assistant": "professional_assistant",
            "engineering_mode": "analyze_image",
            "general_vision": "analyze_image",
            "summarize": "summarize_document",
        }

        for mode_input, expected in alias_cases.items():
            with self.subTest(mode_input=mode_input):
                self.assertEqual(normalize_mode(mode_input), expected)
                self.assertEqual(get_mode(mode_input).id, expected)

"""Canonical assistant mode definitions and alias helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssistantMode:
    """Single assistant mode definition used across UI, CLI, and AI requests."""

    id: str
    name: str
    description: str
    system_prompt: str


MODE_REGISTRY: tuple[AssistantMode, ...] = (
    AssistantMode(
        id="document_reader",
        name="Document Reader",
        description="Extract key text and summarize documents or screens.",
        system_prompt=(
            "You are helping the user quickly read and summarize documents or screen text. "
            "Extract the important content, highlight key points, and summarize clearly."
        ),
    ),
    AssistantMode(
        id="math_solver",
        name="Math Solver",
        description="Solve visible calculations, conversions, and math problems.",
        system_prompt=(
            "You are helping the user solve math problems, unit conversions, measurements, "
            "and quick calculations. Solve the task carefully and show the result clearly."
        ),
    ),
    AssistantMode(
        id="meeting_assistant",
        name="Meeting Assistant",
        description="Explain screen content quickly during fast-paced meetings.",
        system_prompt=(
            "You are helping the user understand screen content quickly during fast-paced "
            "meetings. Focus on the most useful points, decisions, and next steps."
        ),
    ),
    AssistantMode(
        id="engineering_mode",
        name="Engineering Mode",
        description="Analyze diagrams, drawings, technical visuals, and measurements.",
        system_prompt=(
            "You are helping analyze diagrams, drawings, technical visuals, and measurements. "
            "Call out labels, structure, relationships, and notable technical details."
        ),
    ),
    AssistantMode(
        id="general_vision",
        name="General Vision",
        description="Describe what is visible and give the most useful answer.",
        system_prompt=(
            "You are a general AI vision assistant. Explain what is visible and provide "
            "the most useful practical answer."
        ),
    ),
)

MODE_BY_ID: dict[str, AssistantMode] = {mode.id: mode for mode in MODE_REGISTRY}
MODE_ALIASES: dict[str, str] = {
    "read_text": "document_reader",
    "summarize": "document_reader",
    "summarize_document": "document_reader",
    "solve_problem": "math_solver",
    "professional_assistant": "general_vision",
    "analyze_image": "general_vision",
}


def get_canonical_mode_ids() -> tuple[str, ...]:
    """Return canonical mode identifiers in stable display order."""
    return tuple(mode.id for mode in MODE_REGISTRY)


def get_available_modes() -> list[str]:
    """Return the canonical mode choices recommended to users."""
    return list(get_canonical_mode_ids())


def get_mode_definitions() -> tuple[AssistantMode, ...]:
    """Return the ordered assistant mode registry."""
    return MODE_REGISTRY


def get_mode(mode: str) -> AssistantMode:
    """Return the canonical assistant mode metadata for a mode input."""
    return MODE_BY_ID[normalize_mode(mode)]


def get_ui_mode_options() -> tuple[AssistantMode, ...]:
    """Return ordered mode metadata for the touchscreen selector."""
    return MODE_REGISTRY


def normalize_mode(mode: str) -> str:
    """Resolve canonical and legacy mode values into a canonical mode id."""
    if not isinstance(mode, str):
        raise ValueError("Mode must be a string.")

    normalized_mode = mode.strip().lower()
    if not normalized_mode:
        raise ValueError("Mode cannot be empty.")

    canonical_mode = MODE_ALIASES.get(normalized_mode, normalized_mode)
    if canonical_mode not in MODE_BY_ID:
        available_modes = ", ".join(get_available_modes())
        raise ValueError(f"Unsupported mode '{mode}'. Available modes: {available_modes}")

    return canonical_mode


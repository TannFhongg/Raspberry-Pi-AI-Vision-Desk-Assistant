"""Prompt helpers for the Raspberry Pi AI Vision Desk Assistant MVP."""

from __future__ import annotations

MODE_ALIASES: dict[str, str] = {
    "summarize": "summarize_document",
}

PROMPTS: dict[str, str] = {
    "read_text": (
        "Read the visible text in this image and return a concise transcription. "
        "Keep line breaks only when they help readability. If some text is unclear, "
        "briefly note the unreadable parts."
    ),
    "summarize_document": (
        "Summarize the document shown in this image in a concise, beginner-friendly way. "
        "Focus on the main ideas, key headings, and important details."
    ),
    "solve_problem": (
        "Analyze the image and solve the problem shown. Give the final answer first, then "
        "a short explanation of how you reached it. If the problem is unclear, say what is missing."
    ),
    "professional_assistant": (
        "Act as a professional assistant. Analyze the image and provide a concise, practical "
        "response that highlights the most useful information or next step."
    ),
}


def get_available_modes() -> list[str]:
    """Return the supported AI modes in a stable order."""
    return [
        "read_text",
        "summarize",
        "summarize_document",
        "solve_problem",
        "professional_assistant",
    ]


def normalize_mode(mode: str) -> str:
    """Map user-friendly aliases to the canonical internal mode name."""
    normalized_mode = mode.strip().lower()
    return MODE_ALIASES.get(normalized_mode, normalized_mode)


def build_prompt(mode: str, extra_instruction: str | None = None) -> str:
    """Build the final prompt for a given mode."""
    normalized_mode = normalize_mode(mode)
    if normalized_mode not in PROMPTS:
        available_modes = ", ".join(get_available_modes())
        raise ValueError(f"Unsupported mode '{mode}'. Available modes: {available_modes}")

    prompt = PROMPTS[normalized_mode]
    if extra_instruction:
        prompt = f"{prompt}\n\nExtra instruction: {extra_instruction.strip()}"

    return prompt

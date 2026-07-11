"""Hidden backend context builders for assistant modes."""

from __future__ import annotations

from ai.modes import get_mode
from config import SettingsError, load_device_settings

GLOBAL_RESPONSE_GUIDANCE = (
    "You are a professional Raspberry Pi AI vision desk assistant. "
    "The response will be read on a small standalone screen. "
    "Put the most useful information first. "
    "Use concise, practical language. "
    "Use short paragraphs and bullet points when helpful. "
    "If the image is unclear or incomplete, say what is uncertain instead of guessing."
)


def build_mode_context(mode: str, extra_instruction: str | None = None) -> str:
    """Build hidden mode-specific instructions for the OpenAI request."""
    selected_mode = get_mode(mode)
    context_parts = [
        f"Current assistant mode: {selected_mode.name}.",
        selected_mode.system_prompt,
        GLOBAL_RESPONSE_GUIDANCE,
        _build_locale_guidance(),
    ]

    if extra_instruction and extra_instruction.strip():
        context_parts.append(f"Additional internal guidance: {extra_instruction.strip()}")

    return "\n\n".join(context_parts)


def _build_locale_guidance() -> str:
    """Return a locale-specific response hint for future multi-language support."""
    try:
        locale = load_device_settings().localization.locale
    except SettingsError:
        locale = "en"

    if locale == "en":
        return "Default response language: English."
    return f"Default response language locale code: {locale}."

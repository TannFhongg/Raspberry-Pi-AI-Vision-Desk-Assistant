"""Compatibility prompt helpers that delegate to the Phase 13 mode system."""

from __future__ import annotations

from ai.context import build_mode_context
from ai.modes import MODE_ALIASES, get_available_modes, normalize_mode


def build_prompt(mode: str, extra_instruction: str | None = None) -> str:
    """Build hidden instructions for compatibility with older imports."""
    return build_mode_context(mode, extra_instruction)

"""Navigation helpers shared by the Qt controllers."""

from __future__ import annotations

from typing import Any


class NavigationController:
    """Resolve screen transitions for the Qt kiosk workflow."""

    valid_screens = frozenset(
        {"setup", "home", "camera", "processing", "result", "error", "history", "history_detail"}
    )

    @classmethod
    def resolve_render_screen(cls, raw_screen: Any, selected_mode: str) -> str:
        """Resolve the active render screen for the Qt workflow."""
        screen = str(raw_screen or "home").strip().lower()
        if screen not in cls.valid_screens:
            screen = "home"
        if screen == "camera" and not selected_mode:
            return "home"
        if screen in {"home", "camera"} and selected_mode:
            return "camera"
        return screen

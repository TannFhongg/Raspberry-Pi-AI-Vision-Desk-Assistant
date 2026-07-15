"""Display/font selection and non-sensitive Qt screen diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QGuiApplication, QScreen

LOGGER = logging.getLogger(__name__)

BODY_FONT_FALLBACK_ORDER = ("Noto Sans", "Inter", "DejaVu Sans", "Roboto")


def configure_application_font(app: QGuiApplication) -> str:
    """Select the first installed readable body face without making it required."""
    selected = select_body_font_family(QFontDatabase.families(), default="")
    if selected:
        font = QFont(app.font())
        font.setFamily(selected)
        font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
        app.setFont(font)
    return QFontInfo(app.font()).family()


def select_body_font_family(installed_families: list[str], *, default: str) -> str:
    """Resolve the documented body-font order with a clean system fallback."""
    installed = {family.casefold(): family for family in installed_families}
    for candidate in BODY_FONT_FALLBACK_ORDER:
        match = installed.get(candidate.casefold(), "")
        if match:
            return match
    return default


def collect_display_diagnostics(
    screen: QScreen | None,
    *,
    fullscreen_geometry: Any = None,
    selected_font: str = "",
) -> dict[str, str]:
    """Return screen/platform/font details suitable for logs and Device Health."""
    if screen is None:
        return {
            "screen_name": "Unavailable",
            "geometry": "Unavailable",
            "available_geometry": "Unavailable",
            "device_pixel_ratio": "Unavailable",
            "logical_dpi": "Unavailable",
            "physical_dpi": "Unavailable",
            "selected_font_family": selected_font or QFontInfo(QGuiApplication.font()).family(),
            "font_fallback": " > ".join(BODY_FONT_FALLBACK_ORDER),
            "qt_platform": QGuiApplication.platformName() or "unknown",
            "fullscreen_geometry": _format_geometry(fullscreen_geometry),
        }
    return {
        "screen_name": screen.name() or "Unnamed display",
        "geometry": _format_geometry(screen.geometry()),
        "available_geometry": _format_geometry(screen.availableGeometry()),
        "device_pixel_ratio": f"{screen.devicePixelRatio():.2f}",
        "logical_dpi": f"{screen.logicalDotsPerInch():.1f}",
        "physical_dpi": f"{screen.physicalDotsPerInch():.1f}",
        "selected_font_family": selected_font or QFontInfo(QGuiApplication.font()).family(),
        "font_fallback": " > ".join(BODY_FONT_FALLBACK_ORDER),
        "qt_platform": QGuiApplication.platformName() or "unknown",
        "fullscreen_geometry": _format_geometry(fullscreen_geometry),
    }


def log_display_diagnostics(values: dict[str, str]) -> None:
    """Write one non-sensitive display summary to the developer log."""
    LOGGER.info(
        "Display diagnostics: screen=%s geometry=%s available=%s dpr=%s "
        "logical_dpi=%s physical_dpi=%s font=%s fallback=%s platform=%s fullscreen=%s",
        values.get("screen_name", "Unavailable"),
        values.get("geometry", "Unavailable"),
        values.get("available_geometry", "Unavailable"),
        values.get("device_pixel_ratio", "Unavailable"),
        values.get("logical_dpi", "Unavailable"),
        values.get("physical_dpi", "Unavailable"),
        values.get("selected_font_family", "Unavailable"),
        values.get("font_fallback", "Unavailable"),
        values.get("qt_platform", "Unavailable"),
        values.get("fullscreen_geometry", "Unavailable"),
    )


def _format_geometry(value: Any) -> str:
    if value is None or not all(hasattr(value, name) for name in ("x", "y", "width", "height")):
        return "Unavailable"
    return f"{value.width()} x {value.height()} at {value.x()},{value.y()}"

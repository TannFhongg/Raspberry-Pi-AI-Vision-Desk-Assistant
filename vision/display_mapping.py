"""Resolution-independent aspect-fit and preview-coordinate mapping helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DisplayRect:
    x: float
    y: float
    width: float
    height: float


def aspect_fit_rect(container: DisplayRect, source_width: float, source_height: float) -> DisplayRect:
    """Return the source's painted rectangle inside an aspect-fit container."""
    if container.width <= 0 or container.height <= 0 or source_width <= 0 or source_height <= 0:
        return DisplayRect(container.x, container.y, 0.0, 0.0)
    scale = min(container.width / source_width, container.height / source_height)
    painted_width = source_width * scale
    painted_height = source_height * scale
    return DisplayRect(
        container.x + (container.width - painted_width) / 2.0,
        container.y + (container.height - painted_height) / 2.0,
        painted_width,
        painted_height,
    )


def display_to_normalized(x: float, y: float, painted: DisplayRect) -> tuple[float, float]:
    """Map display input to clamped normalized source coordinates."""
    if painted.width <= 0 or painted.height <= 0:
        return 0.0, 0.0
    return (
        _clamp01((x - painted.x) / painted.width),
        _clamp01((y - painted.y) / painted.height),
    )


def normalized_to_display(x: float, y: float, painted: DisplayRect) -> tuple[float, float]:
    """Map normalized source coordinates back into the painted rectangle."""
    return painted.x + _clamp01(x) * painted.width, painted.y + _clamp01(y) * painted.height


def recenter_zoom_region(
    display_x: float,
    display_y: float,
    painted: DisplayRect,
    current_region: DisplayRect,
) -> DisplayRect:
    """Recenter a normalized source region from input inside its painted crop."""
    local_x, local_y = display_to_normalized(display_x, display_y, painted)
    source_x = current_region.x + local_x * current_region.width
    source_y = current_region.y + local_y * current_region.height
    left = min(max(0.0, source_x - current_region.width / 2.0), 1.0 - current_region.width)
    top = min(max(0.0, source_y - current_region.height / 2.0), 1.0 - current_region.height)
    return DisplayRect(left, top, current_region.width, current_region.height)


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))

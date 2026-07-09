"""Detect monitor and document rectangles in captured images."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vision.perspective import compute_warp_size, scale_points

DEFAULT_PREVIEW_MAX_DIMENSION = 1400
MIN_AREA_RATIO = 0.10
MIN_ASPECT_RATIO = 0.50
MAX_ASPECT_RATIO = 3.00


@dataclass(slots=True)
class ScreenDetectionResult:
    """Detected rectangle coordinates in preview and source image space."""

    preview_points: np.ndarray
    source_points: np.ndarray
    area_ratio: float


def detect_screen_region(
    image,
    cv2_module,
    preview_max_dimension: int = DEFAULT_PREVIEW_MAX_DIMENSION,
) -> ScreenDetectionResult | None:
    """Detect the largest plausible monitor or document quadrilateral in an image."""
    preview_image, scale_x, scale_y = build_preview_image(
        image,
        cv2_module=cv2_module,
        preview_max_dimension=preview_max_dimension,
    )
    preview_area = float(preview_image.shape[0] * preview_image.shape[1])
    contours = _find_candidate_contours(preview_image, cv2_module)

    for contour in sorted(contours, key=lambda item: cv2_module.contourArea(item), reverse=True):
        perimeter = cv2_module.arcLength(contour, True)
        approximation = cv2_module.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approximation) != 4 or not cv2_module.isContourConvex(approximation):
            continue

        preview_points = approximation.reshape(4, 2).astype("float32")
        if _is_plausible_rectangle(preview_points, preview_area, cv2_module):
            return _build_result(preview_points, scale_x, scale_y, preview_area, cv2_module)

    if not contours:
        return None

    largest_contour = max(contours, key=lambda item: cv2_module.contourArea(item))
    rect = cv2_module.minAreaRect(largest_contour)
    preview_points = cv2_module.boxPoints(rect).astype("float32")
    if not _is_plausible_rectangle(preview_points, preview_area, cv2_module):
        return None

    return _build_result(preview_points, scale_x, scale_y, preview_area, cv2_module)


def build_preview_image(image, cv2_module, preview_max_dimension: int) -> tuple[object, float, float]:
    """Downscale large images to a preview size for faster contour detection."""
    height, width = image.shape[:2]
    longest_side = max(width, height)
    if longest_side <= preview_max_dimension:
        return image.copy(), 1.0, 1.0

    scale = preview_max_dimension / float(longest_side)
    preview_width = max(1, int(round(width * scale)))
    preview_height = max(1, int(round(height * scale)))
    preview = cv2_module.resize(
        image,
        (preview_width, preview_height),
        interpolation=cv2_module.INTER_AREA,
    )
    return preview, width / float(preview_width), height / float(preview_height)


def draw_detected_region(image, source_points, cv2_module):
    """Draw the detected quadrilateral onto the original image for debugging."""
    overlay = image.copy()
    polygon = np.asarray(source_points, dtype="int32").reshape((-1, 1, 2))
    line_width = max(2, int(round(max(image.shape[:2]) / 400)))
    cv2_module.polylines(overlay, [polygon], isClosed=True, color=(0, 255, 0), thickness=line_width)
    return overlay


def _build_result(preview_points, scale_x: float, scale_y: float, preview_area: float, cv2_module):
    """Create a detection result with source-space coordinates."""
    area_ratio = (
        abs(float(cv2_module.contourArea(preview_points.reshape((-1, 1, 2)))))
        / preview_area
    )
    return ScreenDetectionResult(
        preview_points=preview_points,
        source_points=scale_points(preview_points, scale_x=scale_x, scale_y=scale_y),
        area_ratio=area_ratio,
    )


def _find_candidate_contours(preview_image, cv2_module):
    """Extract strong edge contours from the preview image."""
    if len(preview_image.shape) == 2:
        grayscale = preview_image
    else:
        grayscale = cv2_module.cvtColor(preview_image, cv2_module.COLOR_BGR2GRAY)

    grayscale = cv2_module.GaussianBlur(grayscale, (5, 5), 0)
    grayscale = cv2_module.equalizeHist(grayscale)

    edges = cv2_module.Canny(grayscale, 50, 150)
    kernel = np.ones((5, 5), dtype="uint8")
    edges = cv2_module.morphologyEx(edges, cv2_module.MORPH_CLOSE, kernel, iterations=2)
    edges = cv2_module.dilate(edges, kernel, iterations=1)

    contours_info = cv2_module.findContours(
        edges,
        cv2_module.RETR_LIST,
        cv2_module.CHAIN_APPROX_SIMPLE,
    )
    return contours_info[0] if len(contours_info) == 2 else contours_info[1]


def _is_plausible_rectangle(points, preview_area: float, cv2_module) -> bool:
    """Filter detected quadrilaterals using area and aspect-ratio heuristics."""
    contour_area = abs(float(cv2_module.contourArea(points.reshape((-1, 1, 2)))))
    if contour_area / preview_area < MIN_AREA_RATIO:
        return False

    warp_width, warp_height = compute_warp_size(points)
    if warp_width <= 0 or warp_height <= 0:
        return False

    aspect_ratio = warp_width / float(warp_height)
    return MIN_ASPECT_RATIO <= aspect_ratio <= MAX_ASPECT_RATIO

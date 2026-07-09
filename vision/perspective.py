"""Perspective correction helpers for screen and document crops."""

from __future__ import annotations

import numpy as np


def order_points(points) -> np.ndarray:
    """Return quadrilateral points ordered as top-left, top-right, bottom-right, bottom-left."""
    array = np.asarray(points, dtype="float32")
    if array.shape != (4, 2):
        raise ValueError("Perspective correction requires exactly four 2D points.")

    ordered = np.zeros((4, 2), dtype="float32")
    point_sums = array.sum(axis=1)
    point_diffs = np.diff(array, axis=1).reshape(4)

    ordered[0] = array[np.argmin(point_sums)]
    ordered[2] = array[np.argmax(point_sums)]
    ordered[1] = array[np.argmin(point_diffs)]
    ordered[3] = array[np.argmax(point_diffs)]
    return ordered


def scale_points(points, scale_x: float, scale_y: float) -> np.ndarray:
    """Scale x/y coordinates from preview space back into the original image space."""
    scaled = np.asarray(points, dtype="float32").copy()
    if scaled.shape != (4, 2):
        raise ValueError("Point scaling requires exactly four 2D points.")

    scaled[:, 0] *= float(scale_x)
    scaled[:, 1] *= float(scale_y)
    return scaled


def compute_warp_size(points) -> tuple[int, int]:
    """Compute the target width and height for a perspective-corrected crop."""
    top_left, top_right, bottom_right, bottom_left = order_points(points)

    width_top = float(np.linalg.norm(top_right - top_left))
    width_bottom = float(np.linalg.norm(bottom_right - bottom_left))
    height_right = float(np.linalg.norm(top_right - bottom_right))
    height_left = float(np.linalg.norm(top_left - bottom_left))

    max_width = max(1, int(round(max(width_top, width_bottom))))
    max_height = max(1, int(round(max(height_right, height_left))))
    return max_width, max_height


def four_point_transform(image, points, cv2_module):
    """Warp an image into a front-facing crop defined by four corner points."""
    ordered = order_points(points)
    max_width, max_height = compute_warp_size(ordered)
    destination = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    transform = cv2_module.getPerspectiveTransform(ordered, destination)
    return cv2_module.warpPerspective(image, transform, (max_width, max_height))

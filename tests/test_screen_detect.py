"""Synthetic tests for screen/document rectangle detection."""

from __future__ import annotations

import unittest

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - exercised only on non-OpenCV environments
    cv2 = None
    np = None

from vision.perspective import compute_warp_size
from vision.screen_detect import detect_screen_region


@unittest.skipUnless(cv2 is not None and np is not None, "OpenCV is not available")
class ScreenDetectionTests(unittest.TestCase):
    """Verify synthetic monitor/document detection heuristics."""

    def test_detects_centered_monitor_rectangle(self) -> None:
        image = np.zeros((600, 800, 3), dtype="uint8")
        cv2.rectangle(image, (100, 120), (700, 480), (255, 255, 255), thickness=-1)

        result = detect_screen_region(image, cv2)

        self.assertIsNotNone(result)
        assert result is not None
        width, height = compute_warp_size(result.source_points)
        self.assertGreater(width, 500)
        self.assertGreater(height, 250)
        self.assertGreater(result.area_ratio, 0.2)

    def test_detects_skewed_document_polygon(self) -> None:
        image = np.zeros((700, 900, 3), dtype="uint8")
        polygon = np.array(
            [[170, 120], [720, 150], [650, 560], [210, 520]],
            dtype="int32",
        )
        cv2.fillConvexPoly(image, polygon, (245, 245, 245))

        result = detect_screen_region(image, cv2)

        self.assertIsNotNone(result)
        assert result is not None
        width, height = compute_warp_size(result.source_points)
        self.assertGreater(width, 350)
        self.assertGreater(height, 300)
        self.assertGreater(result.area_ratio, 0.2)

    def test_returns_none_when_no_plausible_rectangle_exists(self) -> None:
        image = np.zeros((500, 700, 3), dtype="uint8")
        cv2.circle(image, (150, 250), 70, (255, 255, 255), thickness=-1)
        cv2.circle(image, (500, 250), 60, (180, 180, 180), thickness=-1)

        result = detect_screen_region(image, cv2)

        self.assertIsNone(result)

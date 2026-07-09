"""Unit tests for perspective geometry helpers."""

from __future__ import annotations

import unittest

import numpy as np

from vision.perspective import compute_warp_size, order_points, scale_points


class PerspectiveGeometryTests(unittest.TestCase):
    """Verify point ordering and warp sizing behavior."""

    def test_order_points_returns_expected_corner_sequence(self) -> None:
        scrambled = np.array(
            [[210, 110], [10, 10], [210, 10], [10, 110]],
            dtype="float32",
        )

        ordered = order_points(scrambled)
        expected = np.array(
            [[10, 10], [210, 10], [210, 110], [10, 110]],
            dtype="float32",
        )
        self.assertTrue(np.allclose(ordered, expected))

    def test_compute_warp_size_uses_longest_edges(self) -> None:
        points = np.array(
            [[20, 20], [220, 10], [230, 130], [10, 140]],
            dtype="float32",
        )

        width, height = compute_warp_size(points)
        self.assertGreaterEqual(width, 200)
        self.assertGreaterEqual(height, 110)

    def test_scale_points_maps_preview_coordinates_back_to_source_space(self) -> None:
        preview_points = np.array(
            [[10, 10], [110, 10], [110, 60], [10, 60]],
            dtype="float32",
        )

        scaled = scale_points(preview_points, scale_x=4.0, scale_y=3.0)
        expected = np.array(
            [[40, 30], [440, 30], [440, 180], [40, 180]],
            dtype="float32",
        )
        self.assertTrue(np.allclose(scaled, expected))

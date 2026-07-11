"""Unit tests for OpenCV camera backend fallback selection."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from camera.capture import _open_opencv_camera


class OpenCVCameraOpeningTests(unittest.TestCase):
    """Verify Linux camera opening prefers V4L2 and can fall back cleanly."""

    def test_linux_prefers_v4l2_when_available(self) -> None:
        opened_calls: list[tuple[int, int | None]] = []

        def build_capture(index, api=None):
            opened_calls.append((index, api))
            return _FakeCamera(opened=True)

        cv2_module = SimpleNamespace(
            CAP_V4L2=200,
            VideoCapture=build_capture,
        )

        with patch("camera.capture.sys.platform", "linux"):
            camera, label = _open_opencv_camera(0, cv2_module)

        self.assertTrue(camera.isOpened())
        self.assertEqual(label, "V4L2")
        self.assertEqual(opened_calls, [(0, 200)])

    def test_linux_falls_back_to_default_when_v4l2_open_fails(self) -> None:
        opened_calls: list[tuple[int, int | None]] = []

        def build_capture(index, api=None):
            opened_calls.append((index, api))
            if api == 200:
                return _FakeCamera(opened=False)
            return _FakeCamera(opened=True)

        cv2_module = SimpleNamespace(
            CAP_V4L2=200,
            VideoCapture=build_capture,
        )

        with patch("camera.capture.sys.platform", "linux"):
            camera, label = _open_opencv_camera(0, cv2_module)

        self.assertTrue(camera.isOpened())
        self.assertEqual(label, "default")
        self.assertEqual(opened_calls, [(0, 200), (0, None)])


class _FakeCamera:
    """Minimal VideoCapture double."""

    def __init__(self, *, opened: bool) -> None:
        self._opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def release(self) -> None:
        self.released = True


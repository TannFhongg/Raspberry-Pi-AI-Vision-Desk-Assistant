"""Unit tests for live preview camera coordination."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from camera.live_preview import (
    DEFAULT_PREVIEW_STREAM_RESOLUTION,
    LivePreviewService,
    _OpenCVFrameSource,
    _OpenCVSnapshotFrameSource,
    _build_preview_resolution,
    _open_frame_source,
)
from hardware.camera_config import CameraControlRequest


class LivePreviewServiceTests(unittest.TestCase):
    """Verify the preview worker releases the camera before capture starts."""

    def test_pause_waits_for_camera_open_to_finish_before_returning(self) -> None:
        request = _build_request()
        source = _ImmediateFrameSource()
        open_started = threading.Event()
        allow_open_to_finish = threading.Event()

        def open_source(_request):
            open_started.set()
            allow_open_to_finish.wait(timeout=2.0)
            return source

        with (
            patch("camera.live_preview.build_camera_request", return_value=request),
            patch("camera.live_preview._open_frame_source", side_effect=open_source),
            patch("camera.live_preview._encode_preview_frame", return_value=b"frame"),
        ):
            service = LivePreviewService(
                backend="opencv",
                camera_index=0,
                width=640,
                height=480,
                autofocus_mode="continuous",
                exposure="auto",
                brightness=0.0,
                frame_interval_seconds=1.0,
            )

            try:
                service.get_jpeg_frame(timeout_seconds=0.01)
                self.assertTrue(open_started.wait(timeout=1.0))

                pause_result: dict[str, bool] = {}
                pause_completed = threading.Event()

                def run_pause() -> None:
                    pause_result["released"] = service.pause(timeout_seconds=1.0)
                    pause_completed.set()

                pause_thread = threading.Thread(target=run_pause, daemon=True)
                pause_thread.start()

                self.assertFalse(pause_completed.wait(timeout=0.1))

                allow_open_to_finish.set()

                self.assertTrue(pause_completed.wait(timeout=1.0))
                pause_thread.join(timeout=1.0)
                self.assertTrue(pause_result["released"])
                self.assertTrue(source.closed_event.wait(timeout=1.0))
                self.assertFalse(source.read_called.is_set())
            finally:
                allow_open_to_finish.set()
                service.close()

    def test_pause_waits_until_worker_releases_camera(self) -> None:
        request = _build_request()
        source = _BlockingFrameSource()

        with (
            patch("camera.live_preview.build_camera_request", return_value=request),
            patch("camera.live_preview._open_frame_source", return_value=source),
            patch("camera.live_preview._encode_preview_frame", return_value=b"frame"),
        ):
            service = LivePreviewService(
                backend="opencv",
                camera_index=0,
                width=640,
                height=480,
                autofocus_mode="continuous",
                exposure="auto",
                brightness=0.0,
                frame_interval_seconds=1.0,
            )

            try:
                service.get_jpeg_frame(timeout_seconds=0.01)
                self.assertTrue(source.read_started.wait(timeout=1.0))

                pause_result: dict[str, bool] = {}
                pause_completed = threading.Event()

                def run_pause() -> None:
                    pause_result["released"] = service.pause(timeout_seconds=1.0)
                    pause_completed.set()

                pause_thread = threading.Thread(target=run_pause, daemon=True)
                pause_thread.start()

                self.assertFalse(pause_completed.wait(timeout=0.1))
                self.assertFalse(source.closed_event.is_set())

                source.allow_read_to_finish.set()

                self.assertTrue(pause_completed.wait(timeout=1.0))
                pause_thread.join(timeout=1.0)
                self.assertTrue(pause_result["released"])
                self.assertTrue(source.closed_event.wait(timeout=1.0))
            finally:
                source.allow_read_to_finish.set()
                service.close()

    def test_pause_times_out_when_camera_is_still_busy(self) -> None:
        request = _build_request()
        source = _BlockingFrameSource()

        with (
            patch("camera.live_preview.build_camera_request", return_value=request),
            patch("camera.live_preview._open_frame_source", return_value=source),
            patch("camera.live_preview._encode_preview_frame", return_value=b"frame"),
        ):
            service = LivePreviewService(
                backend="opencv",
                camera_index=0,
                width=640,
                height=480,
                autofocus_mode="continuous",
                exposure="auto",
                brightness=0.0,
                frame_interval_seconds=1.0,
            )

            try:
                service.get_jpeg_frame(timeout_seconds=0.01)
                self.assertTrue(source.read_started.wait(timeout=1.0))
                self.assertFalse(service.pause(timeout_seconds=0.05))
            finally:
                source.allow_read_to_finish.set()
                service.close()

    def test_build_preview_resolution_prefers_webcam_safe_default_for_large_inputs(self) -> None:
        self.assertEqual(_build_preview_resolution(1920, 1080), DEFAULT_PREVIEW_STREAM_RESOLUTION)

    def test_open_frame_source_prefers_snapshot_mode_on_linux(self) -> None:
        request = _build_request()

        with patch("camera.live_preview.sys.platform", "linux"), patch(
            "camera.live_preview._OpenCVSnapshotFrameSource",
            autospec=True,
        ) as snapshot_source:
            sentinel = object()
            snapshot_source.return_value = sentinel
            source = _open_frame_source(request)

        self.assertIs(source, sentinel)

    def test_open_frame_source_uses_persistent_mode_off_linux(self) -> None:
        request = _build_request()

        with patch("camera.live_preview.sys.platform", "win32"), patch(
            "camera.live_preview._OpenCVFrameSource",
            autospec=True,
        ) as frame_source:
            sentinel = object()
            frame_source.return_value = sentinel
            source = _open_frame_source(request)

        self.assertIs(source, sentinel)

    def test_linux_snapshot_preview_captures_frame_on_demand(self) -> None:
        request = _build_request()

        with (
            patch("camera.live_preview.sys.platform", "linux"),
            patch("camera.live_preview.build_camera_request", return_value=request),
            patch("camera.live_preview.capture_preview_jpeg", return_value=b"frame"),
        ):
            service = LivePreviewService(
                backend="opencv",
                camera_index=0,
                width=640,
                height=480,
                autofocus_mode="continuous",
                exposure="auto",
                brightness=0.0,
                frame_interval_seconds=1.0,
            )

            try:
                frame = service.get_jpeg_frame(timeout_seconds=0.1)
            finally:
                service.close()

        self.assertEqual(frame, b"frame")


class _BlockingFrameSource:
    """Preview source double that blocks reads until the test releases it."""

    def __init__(self) -> None:
        self.read_started = threading.Event()
        self.allow_read_to_finish = threading.Event()
        self.closed_event = threading.Event()

    def read_frame(self):
        self.read_started.set()
        self.allow_read_to_finish.wait(timeout=2.0)
        return object()

    def close(self) -> None:
        self.closed_event.set()


class _ImmediateFrameSource:
    """Preview source double that should be closed before any frame is read."""

    def __init__(self) -> None:
        self.read_called = threading.Event()
        self.closed_event = threading.Event()

    def read_frame(self):
        self.read_called.set()
        return object()

    def close(self) -> None:
        self.closed_event.set()


def _build_request() -> CameraControlRequest:
    """Return a deterministic preview request without loading device settings."""
    return CameraControlRequest(
        backend="opencv",
        camera_index=0,
        width=640,
        height=480,
        autofocus_mode="continuous",
        exposure="auto",
        brightness=0.0,
        capture_delay_seconds=0.0,
    )


if __name__ == "__main__":
    unittest.main()

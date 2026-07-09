"""Command-line test runner for the Phase 2 camera capture pipeline."""

from __future__ import annotations

import argparse
import sys

from camera import CameraCaptureError, capture_image
from config import SettingsError, load_device_settings


def build_parser(settings) -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Capture a test image using Picamera2 or an OpenCV webcam backend."
    )
    parser.add_argument(
        "--backend",
        default=settings.camera.backend,
        choices=("auto", "picamera2", "opencv"),
        help="Camera backend to use.",
    )
    parser.add_argument(
        "--output",
        default="static/captured.jpg",
        help="Path where the captured image will be saved.",
    )
    parser.add_argument(
        "--camera-index",
        default=settings.camera.index,
        type=int,
        help="OpenCV camera index for USB webcam capture.",
    )
    parser.add_argument(
        "--width",
        default=settings.camera.resolution.width,
        type=int,
        help="Requested capture width.",
    )
    parser.add_argument(
        "--height",
        default=settings.camera.resolution.height,
        type=int,
        help="Requested capture height.",
    )
    parser.add_argument(
        "--autofocus-mode",
        default=settings.camera.autofocus_mode,
        choices=("continuous", "auto", "off"),
        help="Autofocus behavior for supported camera backends.",
    )
    parser.add_argument(
        "--exposure",
        default=str(settings.camera.exposure),
        help="Exposure setting: 'auto' or integer microseconds.",
    )
    parser.add_argument(
        "--brightness",
        default=settings.camera.brightness,
        type=float,
        help="Brightness value for supported camera backends.",
    )
    parser.add_argument(
        "--capture-delay",
        default=settings.camera.capture_delay_seconds,
        type=float,
        help="Seconds to wait after camera start before capture.",
    )
    return parser


def main() -> int:
    """Run a one-off terminal camera capture test."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Error: python-dotenv is not installed. Activate your virtual environment and run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    load_dotenv()
    try:
        settings = load_device_settings()
    except SettingsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser = build_parser(settings)
    args = parser.parse_args()

    print("Starting camera capture test...")
    print(f"Requested backend: {args.backend}")

    try:
        result = capture_image(
            output_path=args.output,
            backend=args.backend,
            camera_index=args.camera_index,
            width=args.width,
            height=args.height,
            autofocus_mode=args.autofocus_mode,
            exposure=args.exposure,
            brightness=args.brightness,
            capture_delay_seconds=args.capture_delay,
        )
    except CameraCaptureError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved image to: {result.output_path}")
    print(f"Backend used: {result.backend_used}")
    if result.resolution is not None:
        print(f"Captured resolution: {result.resolution[0]}x{result.resolution[1]}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

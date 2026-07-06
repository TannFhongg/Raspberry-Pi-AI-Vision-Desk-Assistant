"""Command-line test runner for the Phase 2 camera capture pipeline."""

from __future__ import annotations

import argparse
import sys

from camera import CameraCaptureError, capture_image


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Capture a test image using Picamera2 or an OpenCV webcam backend."
    )
    parser.add_argument(
        "--backend",
        default="auto",
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
        default=0,
        type=int,
        help="OpenCV camera index for USB webcam capture.",
    )
    parser.add_argument(
        "--width",
        default=1280,
        type=int,
        help="Requested capture width.",
    )
    parser.add_argument(
        "--height",
        default=720,
        type=int,
        help="Requested capture height.",
    )
    return parser


def main() -> int:
    """Run a one-off terminal camera capture test."""
    parser = build_parser()
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
        )
    except CameraCaptureError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved image to: {result.output_path}")
    print(f"Backend used: {result.backend_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

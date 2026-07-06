"""Command-line test runner for the Phase 6 GPIO button listener."""

from __future__ import annotations

import argparse
import sys

from ai.prompts import get_available_modes
from gpio import GPIOButtonError, GPIOButtonTrigger


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line interface for the GPIO button test."""
    parser = argparse.ArgumentParser(
        description="Listen for a GPIO button press and run the AI Vision pipeline."
    )
    parser.add_argument(
        "--mode",
        default="solve_problem",
        choices=get_available_modes(),
        help="AI mode to use when the button is pressed.",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=("auto", "picamera2", "opencv"),
        help="Camera backend to use for capture.",
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
    parser.add_argument(
        "--grayscale",
        action="store_true",
        help="Convert the image to grayscale during preprocessing.",
    )
    parser.add_argument(
        "--max-dimension",
        default=1600,
        type=int,
        help="Resize only if the image longest side is larger than this value.",
    )
    parser.add_argument(
        "--pin",
        default=17,
        type=int,
        help="GPIO pin connected to the push button.",
    )
    return parser


def main() -> int:
    """Start the GPIO button listener and keep it running until Ctrl+C."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Error: python-dotenv is not installed. Activate your virtual environment and run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    load_dotenv()

    print("GPIO button test started")
    print(f"Button pin: GPIO{args.pin}")
    print(f"Selected AI mode: {args.mode}")
    print(f"Camera backend: {args.backend}")
    print("Press the physical button to run the AI Vision pipeline")
    print("Press Ctrl+C to exit")

    try:
        trigger = GPIOButtonTrigger(
            pin=args.pin,
            mode=args.mode,
            backend=args.backend,
            camera_index=args.camera_index,
            width=args.width,
            height=args.height,
            grayscale=args.grayscale,
            max_dimension=args.max_dimension,
        )
        trigger.start()
        trigger.wait_forever()
    except GPIOButtonError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopping GPIO button test. Goodbye.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

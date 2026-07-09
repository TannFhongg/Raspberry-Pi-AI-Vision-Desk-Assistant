"""Command-line test runner for the Phase 6 GPIO button listener."""

from __future__ import annotations

import argparse
import sys

from ai.prompts import get_available_modes
from config import SettingsError, load_device_settings
from gpio import GPIOButtonError, GPIOButtonTrigger


def build_parser(settings) -> argparse.ArgumentParser:
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
        default=settings.camera.backend,
        choices=("auto", "picamera2", "opencv"),
        help="Camera backend to use for capture.",
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
    grayscale_group = parser.add_mutually_exclusive_group()
    grayscale_group.add_argument(
        "--grayscale",
        dest="grayscale",
        action="store_true",
        help="Convert the image to grayscale during preprocessing.",
    )
    grayscale_group.add_argument(
        "--color",
        dest="grayscale",
        action="store_false",
        help="Keep color preprocessing even if device defaults enable grayscale.",
    )
    parser.set_defaults(grayscale=settings.camera.grayscale)
    parser.add_argument(
        "--max-dimension",
        default=settings.camera.max_dimension,
        type=int,
        help="Resize only if the image longest side is larger than this value.",
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
    parser.add_argument(
        "--pin",
        default=settings.button.pin,
        type=int,
        help="GPIO pin connected to the push button.",
    )
    return parser


def main() -> int:
    """Start the GPIO button listener and keep it running until Ctrl+C."""
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
            autofocus_mode=args.autofocus_mode,
            exposure=args.exposure,
            brightness=args.brightness,
            capture_delay_seconds=args.capture_delay,
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

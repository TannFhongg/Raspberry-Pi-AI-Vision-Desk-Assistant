"""Command-line test runner for long-distance screen/document preprocessing."""

from __future__ import annotations

import argparse
import sys

from config import SettingsError, load_device_settings
from vision import ImagePreprocessError, preprocess_image


def build_parser(settings) -> argparse.ArgumentParser:
    """Create the command-line parser for screen/document preprocessing tests."""
    parser = argparse.ArgumentParser(
        description="Detect, correct, and enhance a distant screen or document photo."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the source image to preprocess.",
    )
    parser.add_argument(
        "--output",
        default="static/processed.jpg",
        help="Path where the processed image will be saved.",
    )
    parser.add_argument(
        "--max-dimension",
        default=settings.camera.max_dimension,
        type=int,
        help="Resize the corrected crop only if its longest side exceeds this value.",
    )
    parser.add_argument(
        "--detect-screen",
        action="store_true",
        help="Detect and crop the monitor/document rectangle before enhancement.",
    )
    parser.add_argument(
        "--enhance",
        action="store_true",
        help="Apply readability-focused text enhancement to the final crop.",
    )
    grayscale_group = parser.add_mutually_exclusive_group()
    grayscale_group.add_argument(
        "--grayscale",
        dest="grayscale",
        action="store_true",
        help="Convert the final enhanced image to grayscale.",
    )
    grayscale_group.add_argument(
        "--color",
        dest="grayscale",
        action="store_false",
        help="Keep the final enhanced image in color.",
    )
    parser.set_defaults(grayscale=settings.camera.grayscale)
    return parser


def main() -> int:
    """Run a one-off distant screen/document preprocessing test."""
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

    detect_screen = args.detect_screen
    enhance = args.enhance
    if not detect_screen and not enhance:
        detect_screen = True
        enhance = True

    print("Starting screen/document vision test...")
    print(f"Input image: {args.input}")
    print(f"Output image: {args.output}")
    print(f"Screen detection: {'on' if detect_screen else 'off'}")
    print(f"Text enhancement: {'on' if enhance else 'off'}")
    print(f"Grayscale mode: {'on' if args.grayscale else 'off'}")

    try:
        result = preprocess_image(
            input_path=args.input,
            output_path=args.output,
            grayscale=args.grayscale,
            max_dimension=args.max_dimension,
            detect_screen=detect_screen,
            enhance_text=enhance,
        )
    except ImagePreprocessError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Screen/document preprocessing completed successfully.")
    print(f"Original size: {result.original_size[0]}x{result.original_size[1]}")
    print(f"Processed size: {result.processed_size[0]}x{result.processed_size[1]}")
    print(f"Screen detected: {'yes' if result.screen_detected else 'no'}")
    print(f"Perspective corrected: {'yes' if result.perspective_corrected else 'no'}")
    if result.debug_dir is not None:
        print(f"Debug images saved to: {result.debug_dir}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print(f"Saved processed image to: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

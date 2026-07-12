"""Command-line test runner for the Phase 3 preprocessing pipeline."""

from __future__ import annotations

import argparse
import sys

from config import SettingsError, load_device_settings
from vision import ImagePreprocessError, preprocess_image


def build_parser(settings) -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Load a sample image, preprocess it, and save the output to debug/processed.jpg."
    )
    parser.add_argument(
        "--input",
        default="test_images/document.jpg",
        help="Path to the source image captured from the camera.",
    )
    parser.add_argument(
        "--output",
        default="debug/processed.jpg",
        help="Path where the processed image will be saved.",
    )
    parser.add_argument(
        "--max-dimension",
        default=settings.camera.max_dimension,
        type=int,
        help="Resize the image only if its longest side is larger than this value.",
    )
    grayscale_group = parser.add_mutually_exclusive_group()
    grayscale_group.add_argument(
        "--grayscale",
        dest="grayscale",
        action="store_true",
        help="Convert the image to grayscale before contrast and sharpening.",
    )
    grayscale_group.add_argument(
        "--color",
        dest="grayscale",
        action="store_false",
        help="Keep color preprocessing even if device defaults enable grayscale.",
    )
    parser.set_defaults(grayscale=settings.camera.grayscale)
    return parser


def main() -> int:
    """Run a one-off preprocessing test from the terminal."""
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

    print("Starting image preprocessing test...")
    print(f"Input image: {args.input}")
    print(f"Output image: {args.output}")
    print(f"Grayscale mode: {'on' if args.grayscale else 'off'}")

    try:
        result = preprocess_image(
            input_path=args.input,
            output_path=args.output,
            grayscale=args.grayscale,
            max_dimension=args.max_dimension,
        )
    except ImagePreprocessError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Preprocessing completed successfully.")
    print(
        f"Original size: {result.original_size[0]}x{result.original_size[1]}"
    )
    print(
        f"Processed size: {result.processed_size[0]}x{result.processed_size[1]}"
    )
    print(f"Saved processed image to: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

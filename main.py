"""Phase 4 terminal pipeline for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import argparse
import sys

from ai.prompts import get_available_modes
from pipeline import PipelineError, run_capture_analyze


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line interface for the full terminal pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the full camera -> preprocess -> OpenAI Vision terminal pipeline."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=get_available_modes(),
        help="AI mode to use for the final analysis.",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=("auto", "picamera2", "opencv"),
        help="Camera backend to use for image capture.",
    )
    parser.add_argument(
        "--camera-index",
        default=0,
        type=int,
        help="OpenCV camera index for USB webcam capture.",
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
    return parser


def main() -> int:
    """Run the end-to-end terminal pipeline and print the final AI answer."""
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

    print("Starting AI Vision pipeline...")
    print(f"Mode selected: {args.mode}")

    try:
        result = run_capture_analyze(
            mode=args.mode,
            backend=args.backend,
            camera_index=args.camera_index,
            grayscale=args.grayscale,
            max_dimension=args.max_dimension,
            status_callback=print,
        )
    except PipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Answer received.")
    print(f"Camera backend used: {result.camera_backend_used}")
    print(f"Captured image saved to: {result.captured_path}")
    print(f"Processed image saved to: {result.processed_path}")
    print("\nAI Answer:\n")
    print(result.answer or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

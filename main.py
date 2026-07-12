"""Phase 4 terminal pipeline for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ai.prompts import get_available_modes, normalize_mode
from config import SettingsError, load_device_settings
from pipeline import PipelineError, run_analyze, run_capture_analyze, run_preprocess
from system import configure_logging
from visiondesk.paths import resolve_visiondesk_paths

_DEFAULT_PATHS = resolve_visiondesk_paths()
CAPTURED_IMAGE_PATH = _DEFAULT_PATHS.private_current_path / "captured.jpg"
PROCESSED_IMAGE_PATH = _DEFAULT_PATHS.private_current_path / "processed.jpg"
LOGGER = logging.getLogger(__name__)


def build_parser(settings) -> argparse.ArgumentParser:
    """Create the command-line interface for the full terminal pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the full camera -> preprocess -> OpenAI Vision terminal pipeline."
    )
    parser.add_argument(
        "--mode",
        required=True,
        type=normalize_mode,
        choices=get_available_modes(),
        help="Assistant mode to use for the final analysis. Legacy mode aliases are also accepted.",
    )
    parser.add_argument(
        "--backend",
        default=settings.camera.backend,
        choices=("opencv",),
        help="Camera backend to use for USB webcam capture.",
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
        "--max-dimension",
        default=settings.camera.max_dimension,
        type=int,
        help="Resize only if the image longest side is larger than this value.",
    )
    parser.add_argument(
        "--screen-optimization",
        default=settings.vision.screen_optimization,
        choices=("auto", "on", "off"),
        help="Control long-distance screen/document optimization behavior.",
    )
    parser.add_argument(
        "--skip-capture",
        action="store_true",
        help="Reuse the current captured image instead of capturing a new image first.",
    )
    return parser


def main() -> int:
    """Run the end-to-end terminal pipeline and print the final AI answer."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Error: python-dotenv is not installed. Activate your virtual environment and run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    load_dotenv(_DEFAULT_PATHS.env_file_path, override=False)
    try:
        settings = load_device_settings()
    except SettingsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    configure_logging(settings=settings)
    LOGGER.info("CLI startup begin")
    parser = build_parser(settings)
    args = parser.parse_args()
    LOGGER.info("CLI startup complete mode=%s skip_capture=%s", args.mode, args.skip_capture)
    print("Starting AI Vision pipeline...")
    print(f"Mode selected: {args.mode}")

    try:
        if args.skip_capture:
            if not CAPTURED_IMAGE_PATH.is_file():
                raise PipelineError(
                    "No captured image found. Please copy a test image to the current capture path or run camera capture first."
                )

            print(f"Using existing captured image: {CAPTURED_IMAGE_PATH}")
            preprocess_result = run_preprocess(
                input_path=str(CAPTURED_IMAGE_PATH),
                output_path=str(PROCESSED_IMAGE_PATH),
                mode=args.mode,
                grayscale=args.grayscale,
                max_dimension=args.max_dimension,
                screen_optimization=args.screen_optimization,
                status_callback=print,
            )
            result = run_analyze(
                mode=args.mode,
                captured_path=str(CAPTURED_IMAGE_PATH),
                processed_path=str(preprocess_result.processed_path or PROCESSED_IMAGE_PATH),
                grayscale=args.grayscale,
                max_dimension=args.max_dimension,
                screen_optimization=args.screen_optimization,
                status_callback=print,
            )
            result.warnings = (*preprocess_result.warnings, *result.warnings)
        else:
            result = run_capture_analyze(
                mode=args.mode,
                backend=args.backend,
                camera_index=args.camera_index,
                width=args.width,
                height=args.height,
                grayscale=args.grayscale,
                max_dimension=args.max_dimension,
                screen_optimization=args.screen_optimization,
                autofocus_mode=args.autofocus_mode,
                exposure=args.exposure,
                brightness=args.brightness,
                capture_delay_seconds=args.capture_delay,
                status_callback=print,
            )
    except PipelineError as exc:
        LOGGER.error("CLI pipeline failed: %s", exc, exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Answer received.")
    if args.skip_capture:
        print(f"Captured image used: {result.captured_path}")
    else:
        print(f"Camera backend used: {result.camera_backend_used}")
        print(f"Captured image saved to: {result.captured_path}")
        if result.camera_resolution is not None:
            print(
                f"Captured resolution: {result.camera_resolution[0]}x{result.camera_resolution[1]}"
            )
    print(f"Processed image saved to: {result.processed_path}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print("\nAI Answer:\n")
    print(result.answer or "")
    LOGGER.info("CLI pipeline completed successfully mode=%s", args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
